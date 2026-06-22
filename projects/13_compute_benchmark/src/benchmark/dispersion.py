"""Statistiques de dispersion inter-venues — la **mesure**, jamais le signal de timing.

Ce que publie la vitrine : à quel point les marketplaces s'écartent du prix de référence
(spread, %, coefficient de variation) et, en descriptif sur la fenêtre, **quelle venue
est en moyenne moins chère** (``venue_levels``). Ce qu'elle ne publie PAS : un signal live
« louer sur X maintenant » (edge privé, cf. ``CLAUDE.md`` §frontière edge).

:func:`venue_rates_at` **reproduit volontairement** la réduction par-venue de
:func:`core.ingestion.build_spot_index` (mêmes staleness, type de bail, exclusions,
point-in-time, médiane de la cohorte la plus fraîche). ``core`` étant en lecture seule
pour cette couche, l'invariant anti-dérive est garanti par un test dédié :
``estimator(filter(venue_rates_at(...))) == build_spot_index(...).price``.
"""

from __future__ import annotations

import datetime as dt
import statistics
from collections import defaultdict
from dataclasses import dataclass
from typing import Sequence

from core.ingestion.compute_index import (
    DEFAULT_INDEX_CONFIG,
    IndexConfig,
    InsufficientDataError,
    build_spot_index,
)
from core.ingestion.protocols import Snapshot, VenueRate, ensure_utc


def venue_rates_at(
    snapshots: Sequence[Snapshot],
    as_of: dt.datetime,
    gpu_model: str,
    *,
    config: IndexConfig = DEFAULT_INDEX_CONFIG,
) -> list[VenueRate]:
    """Taux par-venue entrant dans l'indice à ``as_of`` (miroir de ``build_spot_index``).

    Applique les mêmes filtres (staleness, ``lease_type``, sources exclues, point-in-time)
    puis réduit, par source, la cohorte la plus fraîche à sa médiane (disponibilité sommée).
    Le rejet d'outliers (``config.outlier_filter``) n'est **pas** appliqué ici : il l'est
    par l'appelant, comme dans le cœur, pour pouvoir décrire aussi les venues écartées.
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


@dataclass(frozen=True)
class DispersionPoint:
    """Dispersion inter-venues à un instant pour un modèle (réel, point-in-time).

    Mesure descriptive de l'écart entre marketplaces autour du prix de référence.
    ``n_venues < 2`` → dispersion **indéfinie** (champs d'écart à ``None``, ``is_defined``
    faux) : un benchmark mono-venue n'a pas de dispersion, on l'assume plutôt que l'inventer.
    """

    as_of: dt.datetime
    gpu_model: str
    n_venues: int
    index_price: float
    spread_abs: float | None
    spread_pct: float | None
    cv: float | None
    cheapest_venue: str | None
    dearest_venue: str | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "as_of", ensure_utc(self.as_of))

    @property
    def is_defined(self) -> bool:
        """Vrai ssi au moins deux venues constituent l'indice (dispersion calculable)."""
        return self.n_venues >= 2


def dispersion_at(
    snapshots: Sequence[Snapshot],
    as_of: dt.datetime,
    gpu_model: str,
    *,
    config: IndexConfig = DEFAULT_INDEX_CONFIG,
) -> DispersionPoint:
    """Dispersion des venues constituant l'indice de ``gpu_model`` à ``as_of``.

    Calculée sur les venues **retenues** par l'indice (après rejet d'outliers), pour
    décrire l'écart vu par le prix publié. ``spread_pct`` est relatif au prix de l'indice ;
    ``cv`` est le coefficient de variation population (écart-type / moyenne).

    Raises
    ------
    InsufficientDataError
        Si aucun fix n'est calculable à ``as_of`` (propagé depuis ``build_spot_index``).
    """
    as_of = ensure_utc(as_of)
    kept = config.outlier_filter.filter(venue_rates_at(snapshots, as_of, gpu_model, config=config))
    index_price = build_spot_index(snapshots, as_of, gpu_model, config=config).price_usd_per_hour

    if len(kept) < 2:
        return DispersionPoint(
            as_of=as_of,
            gpu_model=gpu_model,
            n_venues=len(kept),
            index_price=index_price,
            spread_abs=None,
            spread_pct=None,
            cv=None,
            cheapest_venue=None,
            dearest_venue=None,
        )

    prices = [r.rate for r in kept]
    spread_abs = max(prices) - min(prices)
    return DispersionPoint(
        as_of=as_of,
        gpu_model=gpu_model,
        n_venues=len(kept),
        index_price=index_price,
        spread_abs=spread_abs,
        spread_pct=spread_abs / index_price,
        cv=statistics.pstdev(prices) / statistics.mean(prices),
        cheapest_venue=min(kept, key=lambda r: r.rate).source,
        dearest_venue=max(kept, key=lambda r: r.rate).source,
    )


@dataclass(frozen=True)
class VenueLevel:
    """Niveau moyen d'une venue nommée sur une fenêtre (mesure « qui est moins cher »).

    Descriptif et fenêtré — ce n'est **pas** un signal de timing live : il dit « vastai a
    coté ~X % sous l'indice en moyenne », pas « louer sur vastai à l'instant t ».
    """

    source: str
    mean_rate: float
    mean_discount_vs_index: float
    n_fixes: int


def venue_levels(
    snapshots: Sequence[Snapshot],
    as_of_grid: Sequence[dt.datetime],
    gpu_model: str,
    *,
    config: IndexConfig = DEFAULT_INDEX_CONFIG,
) -> list[VenueLevel]:
    """Niveau moyen et escompte moyen vs indice, par venue nommée, sur ``as_of_grid``.

    Pour chaque fix calculable, accumule (taux de la venue retenue, prix de l'indice) puis
    moyenne par venue. ``mean_discount_vs_index`` est la moyenne des escomptes par-fix
    ``(taux − indice) / indice`` (négatif = moins cher que la référence).
    """
    acc: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for as_of in as_of_grid:
        try:
            index_price = build_spot_index(
                snapshots, as_of, gpu_model, config=config
            ).price_usd_per_hour
        except InsufficientDataError:
            continue
        kept = config.outlier_filter.filter(
            venue_rates_at(snapshots, as_of, gpu_model, config=config)
        )
        for r in kept:
            acc[r.source].append((r.rate, index_price))

    levels = [
        VenueLevel(
            source=source,
            mean_rate=statistics.mean(rate for rate, _ in pairs),
            mean_discount_vs_index=statistics.mean((rate - idx) / idx for rate, idx in pairs),
            n_fixes=len(pairs),
        )
        for source, pairs in acc.items()
    ]
    return sorted(levels, key=lambda lv: lv.source)
