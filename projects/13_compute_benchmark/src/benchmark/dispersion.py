"""Cross-venue dispersion statistics — the **measurement**, never the timing signal.

What the showcase publishes: how far marketplaces deviate from the reference price
(spread, %, coefficient of variation) and, descriptively over the window, **which venue
is cheaper on average** (``venue_levels``). What it does NOT publish: a live signal
"rent on X now" (private edge, cf. ``CLAUDE.md`` §edge boundary).

:func:`venue_rates_at` **deliberately reproduces** the per-venue reduction of
:func:`core.ingestion.build_spot_index` (same staleness, lease type, exclusions,
point-in-time, median of the freshest cohort). Since ``core`` is read-only
for this layer, the anti-drift invariant is guaranteed by a dedicated test:
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
    """Per-venue rates entering the index at ``as_of`` (mirrors ``build_spot_index``).

    Applies the same filters (staleness, ``lease_type``, excluded sources, point-in-time)
    then reduces, per source, the freshest cohort to its median (availability summed).
    Outlier rejection (``config.outlier_filter``) is **not** applied here: it is applied
    by the caller, as in the core, so that excluded venues can also be described.
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
    """Cross-venue dispersion at an instant for a model (real, point-in-time).

    Descriptive measurement of the gap between marketplaces around the reference price.
    ``n_venues < 2`` → dispersion **undefined** (spread fields set to ``None``, ``is_defined``
    false): a single-venue benchmark has no dispersion, we acknowledge that rather than invent it.
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
        """True iff at least two venues make up the index (dispersion computable)."""
        return self.n_venues >= 2


def dispersion_at(
    snapshots: Sequence[Snapshot],
    as_of: dt.datetime,
    gpu_model: str,
    *,
    config: IndexConfig = DEFAULT_INDEX_CONFIG,
) -> DispersionPoint:
    """Dispersion of the venues making up the index for ``gpu_model`` at ``as_of``.

    Computed on the venues **retained** by the index (after outlier rejection), to
    describe the gap seen by the published price. ``spread_pct`` is relative to the index price;
    ``cv`` is the population coefficient of variation (standard deviation / mean).

    Raises
    ------
    InsufficientDataError
        If no fix is computable at ``as_of`` (propagated from ``build_spot_index``).
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
    """Average level of a named venue over a window (measurement of "who is cheaper").

    Descriptive and windowed — this is **not** a live timing signal: it says "vastai
    quoted ~X% below the index on average", not "rent on vastai at instant t".
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
    """Average level and average discount vs. index, per named venue, over ``as_of_grid``.

    For each computable fix, accumulates (retained venue's rate, index price) then
    averages per venue. ``mean_discount_vs_index`` is the mean of the per-fix discounts
    ``(rate − index) / index`` (negative = cheaper than the reference).
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
