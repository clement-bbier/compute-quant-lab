"""Construction de l'indice spot compute (point-in-time, configurable).

``build_spot_index`` agrège des relevés multi-venues en un prix canonique $/GPU·h,
selon une :class:`IndexConfig` injectable. Le défaut ``DEFAULT_INDEX_CONFIG`` reproduit
le standard des meilleurs acteurs (GPU Markets / Silicon Data, settlement des futures
compute CME) : trimmed mean 20 % + rejet 2.5 MAD, fenêtre 24 h **sans carry-forward**,
exclusion des list prices hyperscalers, séparation des types de bail.

Garanties point-in-time : seules les observations ``snapshotted_at <= as_of`` entrent
dans le fix, et aucune venue périmée (> fenêtre de staleness) n'est forward-fillée.

Deux sources concrètes implémentent :class:`ComputeIndexSource` :

- :class:`MarketplaceProxySource` — réel, PoC : lit les snapshots accumulés (Vast.ai/
  RunPod) via un :class:`SnapshotStore`.
- :class:`SiliconDataSource` — source canonique (indice SDH100RT) ; stub documenté
  token-gated, branchable sans toucher au cœur (OCP).
"""

from __future__ import annotations

import datetime as dt
import os
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Sequence

from core.ingestion.estimators import MadOutlierFilter, TrimmedMean
from core.ingestion.protocols import (
    IndexEstimator,
    OutlierFilter,
    Snapshot,
    SnapshotStore,
    SpotIndexPoint,
    VenueRate,
    ensure_utc,
)

# List prices hyperscalers : reportées ailleurs mais exclues de l'estimateur (standard marché).
HYPERSCALERS: frozenset[str] = frozenset({"aws", "gcp", "azure"})


class InsufficientDataError(RuntimeError):
    """Levée quand aucune venue fraîche ne permet de calculer un fix (no carry-forward)."""


@dataclass(frozen=True)
class IndexConfig:
    """Paramètres injectables de construction de l'indice (tout est configurable).

    Les valeurs par défaut de ``DEFAULT_INDEX_CONFIG`` encodent le standard de marché ;
    P03/P05/P06 peuvent permuter estimateur, filtre, fenêtre… sans forker le cœur.
    """

    estimator: IndexEstimator
    outlier_filter: OutlierFilter
    staleness: dt.timedelta = dt.timedelta(hours=24)
    lease_type: str = "on_demand"
    excluded_sources: frozenset[str] = HYPERSCALERS
    min_sources: int = 1

    @property
    def method(self) -> str:
        """Identifiant auditable de la config, tracé dans ``SpotIndexPoint.method``."""
        return f"{self.estimator.name}+{self.outlier_filter.name}"


DEFAULT_INDEX_CONFIG = IndexConfig(
    estimator=TrimmedMean(0.20),
    outlier_filter=MadOutlierFilter(2.5),
)


def build_spot_index(
    snapshots: Sequence[Snapshot],
    as_of: dt.datetime,
    gpu_model: str,
    *,
    config: IndexConfig = DEFAULT_INDEX_CONFIG,
) -> SpotIndexPoint:
    """Calcule l'indice spot canonique pour ``gpu_model`` à l'instant ``as_of``.

    Parameters
    ----------
    snapshots
        Relevés bruts (toutes sources/modèles confondus) ; filtrés ici.
    as_of
        Instant du fix (UTC). Aucune observation postérieure n'est utilisée (anti look-ahead).
    gpu_model
        Modèle agrégé (ex. ``"H100"``).
    config
        Stratégies et paramètres d'agrégation. Défaut : standard marché.

    Returns
    -------
    SpotIndexPoint
        Prix canonique + métadonnées d'audit (méthode, nb de venues, plus vieux relevé).

    Raises
    ------
    InsufficientDataError
        Si aucune venue fraîche ne subsiste après filtres et rejet d'outliers.
    """
    as_of = ensure_utc(as_of)
    cutoff = as_of - config.staleness

    relevant = [
        s
        for s in snapshots
        if s.gpu_model == gpu_model
        and s.lease_type == config.lease_type
        and s.source not in config.excluded_sources
        and cutoff <= s.snapshotted_at <= as_of  # staleness + point-in-time
    ]

    # Une venue ne pèse qu'une fois : on agrège la DISTRIBUTION de sa cohorte la plus
    # fraîche (médiane robuste) au lieu de retenir une offre arbitraire sur égalité de
    # timestamp. L'agrégation INTER-venues reste la responsabilité de l'estimateur.
    offers_by_source: dict[str, list[Snapshot]] = defaultdict(list)
    for s in relevant:
        offers_by_source[s.source].append(s)

    venue_rates: list[VenueRate] = []
    for source, offers in offers_by_source.items():
        latest_at = max(o.snapshotted_at for o in offers)
        cohort = [o for o in offers if o.snapshotted_at == latest_at]
        venue_rates.append(
            VenueRate(
                source=source,
                rate=statistics.median(o.price_usd_per_hour for o in cohort),
                availability=sum(o.availability for o in cohort),
                snapshotted_at=latest_at,
            )
        )
    if not venue_rates:
        raise InsufficientDataError(
            f"Aucune venue fraîche pour {gpu_model}/{config.lease_type} à {as_of.isoformat()} "
            f"(fenêtre {config.staleness}) : pas de fix (no carry-forward)."
        )

    kept = config.outlier_filter.filter(venue_rates)
    if len(kept) < config.min_sources:
        raise InsufficientDataError(
            f"Trop peu de venues ({len(kept)} < {config.min_sources}) après rejet d'outliers "
            f"pour {gpu_model}/{config.lease_type} à {as_of.isoformat()}."
        )

    price = config.estimator.estimate(kept)
    oldest_obs_at = min(r.snapshotted_at for r in kept)

    return SpotIndexPoint(
        as_of=as_of,
        gpu_model=gpu_model,
        lease_type=config.lease_type,
        price_usd_per_hour=price,
        n_sources=len(kept),
        method=config.method,
        oldest_obs_at=oldest_obs_at,
    )


@dataclass(frozen=True)
class MarketplaceProxySource:
    """Source réelle (PoC) : indice spot dérivé des snapshots marketplace accumulés.

    Les prix Vast.ai/RunPod sont des données *réelles* relevées maison ; cette source
    sert de proxy de l'indice canonique en attendant le branchement Silicon Data.
    """

    store: SnapshotStore

    def fetch(self, start: dt.datetime, end: dt.datetime) -> Sequence[Snapshot]:
        start, end = ensure_utc(start), ensure_utc(end)
        return [s for s in self.store.load() if start <= s.snapshotted_at <= end]


@dataclass(frozen=True)
class SiliconDataSource:
    """Source canonique Silicon Data (indice SDH100RT) — stub documenté, token-gated.

    Branchement réel en attente de la spec d'API et du token ``SILICONDATA_API_TOKEN``.
    Présent ici pour fixer le contrat (OCP) : remplacer ``fetch`` par l'appel HTTP réel
    suffira, sans modifier ``build_spot_index`` ni les consommateurs.
    """

    api_token: str | None = field(default=None)

    def __post_init__(self) -> None:
        if self.api_token is None:
            object.__setattr__(self, "api_token", os.environ.get("SILICONDATA_API_TOKEN"))

    def fetch(self, start: dt.datetime, end: dt.datetime) -> Sequence[Snapshot]:
        raise NotImplementedError(
            "Source canonique Silicon Data (SDH100RT) non branchée. "
            "Requiert SILICONDATA_API_TOKEN + endpoint d'API ; renvoyer des Snapshot "
            "source='silicon_data'. Cf. handoff convergence (registre des sources)."
        )
