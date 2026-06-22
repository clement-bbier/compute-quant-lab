"""Couche vue — la **mesure** publique (lecture pure du cold store).

Consomme le lac de prix versionné via le Protocol ``SnapshotStore`` (injecté) et en
dérive deux objets que le produit affiche, **tous deux point-in-time** :

- :class:`MarketView` — photo à ``as_of`` : venues retenues triées + indice canonique ;
- :func:`price_curve` — série de l'indice par modèle dans le temps.

Frontière edge : ceci ne fait **que mesurer** (« qui est le moins cher, à quel niveau »).
La **décision** (« louer maintenant ») est un signal injecté, hors de ce module
(cf. ``signal_iface``). Aucune réécriture de ``core/`` : pur consommateur.

L'indice canonique et l'anti look-ahead sont **délégués** à
:func:`core.ingestion.compute_index.build_spot_index` (déjà testé) ; seule la réduction
par-venue (pour le *ranking* « moins cher ») est reprise ici, car ``core`` n'expose pas
les taux par-venue. → handoff convergence : promouvoir un helper ``venue_rates`` dans
``core.ingestion``.
"""

from __future__ import annotations

import datetime as dt
import statistics
from collections import defaultdict
from dataclasses import dataclass
from typing import Sequence

import pandas as pd

from core.ingestion.compute_index import (
    DEFAULT_INDEX_CONFIG,
    IndexConfig,
    InsufficientDataError,
    build_spot_index,
)
from core.ingestion.protocols import Snapshot, SnapshotStore, VenueRate, ensure_utc

#: Colonnes de la courbe d'indice renvoyée par :func:`price_curve`.
CURVE_COLUMNS: list[str] = ["as_of", "index_price", "n_sources"]


@dataclass(frozen=True)
class MarketView:
    """Photo point-in-time d'un modèle GPU : venues retenues + indice canonique.

    Les ``venues`` sont déjà **filtrées** (mêmes outliers rejetés que l'indice) et
    **triées** par prix croissant : ``cheapest`` est donc la venue la moins chère
    *crédible* à ``as_of`` (un relevé aberrant n'est jamais présenté comme la moins chère).
    """

    as_of: dt.datetime
    gpu_model: str
    venues: tuple[VenueRate, ...]
    index_price: float
    method: str

    def __post_init__(self) -> None:
        if not self.venues:
            raise ValueError("MarketView sans venue : état illégal (utiliser read_market).")

    @property
    def cheapest(self) -> VenueRate:
        """Venue la moins chère parmi les venues retenues (``venues`` est trié)."""
        return self.venues[0]

    @property
    def median_rate(self) -> float:
        """Médiane des taux inter-venues retenus ($/GPU·h)."""
        return statistics.median(v.rate for v in self.venues)


def _venue_rates(
    snapshots: Sequence[Snapshot],
    as_of: dt.datetime,
    gpu_model: str,
    config: IndexConfig,
) -> list[VenueRate]:
    """Réduit les snapshots en un taux par venue (cohorte la plus fraîche).

    Reprend la logique de :func:`build_spot_index` (staleness + point-in-time + exclusion
    hyperscalers + type de bail) afin d'exposer les taux *par-venue* nécessaires au ranking
    produit, que ``core`` ne renvoie pas.
    """
    as_of = ensure_utc(as_of)
    cutoff = as_of - config.staleness
    relevant = [
        s
        for s in snapshots
        if s.gpu_model == gpu_model
        and s.lease_type == config.lease_type
        and s.source not in config.excluded_sources
        and cutoff <= s.snapshotted_at <= as_of
    ]
    offers_by_source: dict[str, list[Snapshot]] = defaultdict(list)
    for s in relevant:
        offers_by_source[s.source].append(s)

    rates: list[VenueRate] = []
    for source, offers in offers_by_source.items():
        latest_at = max(o.snapshotted_at for o in offers)
        cohort = [o for o in offers if o.snapshotted_at == latest_at]
        rates.append(
            VenueRate(
                source=source,
                rate=statistics.median(o.price_usd_per_hour for o in cohort),
                availability=sum(o.availability for o in cohort),
                snapshotted_at=latest_at,
            )
        )
    return rates


def read_market(
    store: SnapshotStore,
    as_of: dt.datetime,
    gpu_model: str,
    *,
    config: IndexConfig = DEFAULT_INDEX_CONFIG,
) -> MarketView:
    """Construit la :class:`MarketView` point-in-time de ``gpu_model`` à ``as_of``.

    Parameters
    ----------
    store
        Source de snapshots (cold store réel ou double de test) — injectée (DI).
    as_of
        Instant du fix (UTC tz-aware). Aucune observation postérieure n'est utilisée.
    gpu_model
        Modèle agrégé (ex. ``"H100"``).
    config
        Config d'agrégation (estimateur + filtre + staleness). Défaut : standard marché.

    Returns
    -------
    MarketView
        Venues retenues triées + indice canonique.

    Raises
    ------
    InsufficientDataError
        Si aucune venue fraîche ne permet de calculer un fix (propagé de ``build_spot_index``).
    """
    as_of = ensure_utc(as_of)
    snapshots = store.load()
    # Indice canonique + validation (no carry-forward, anti look-ahead) délégués à core.
    point = build_spot_index(snapshots, as_of, gpu_model, config=config)
    kept = config.outlier_filter.filter(_venue_rates(snapshots, as_of, gpu_model, config))
    venues = tuple(sorted(kept, key=lambda v: v.rate))
    return MarketView(
        as_of=as_of,
        gpu_model=gpu_model,
        venues=venues,
        index_price=point.price_usd_per_hour,
        method=point.method,
    )


def price_curve(
    store: SnapshotStore,
    gpu_model: str,
    timestamps: Sequence[dt.datetime],
    *,
    config: IndexConfig = DEFAULT_INDEX_CONFIG,
) -> pd.DataFrame:
    """Série de l'indice canonique de ``gpu_model`` aux ``timestamps`` (point-in-time).

    Chaque point est calculé par :func:`build_spot_index` sur les seules observations
    ``<= t`` : la courbe est anti look-ahead par construction. Un instant sans donnée
    suffisante rend ``index_price = NaN`` et ``n_sources = 0`` (dégradation propre, pas
    de carry-forward).

    Returns
    -------
    pandas.DataFrame
        Colonnes :data:`CURVE_COLUMNS` (``as_of``, ``index_price``, ``n_sources``).
    """
    snapshots = store.load()
    records: list[dict[str, object]] = []
    for raw in timestamps:
        t = ensure_utc(raw)
        try:
            point = build_spot_index(snapshots, t, gpu_model, config=config)
            records.append(
                {"as_of": t, "index_price": point.price_usd_per_hour, "n_sources": point.n_sources}
            )
        except InsufficientDataError:
            records.append({"as_of": t, "index_price": float("nan"), "n_sources": 0})
    return pd.DataFrame.from_records(records, columns=CURVE_COLUMNS)
