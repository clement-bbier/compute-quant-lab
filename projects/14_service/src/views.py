"""View layer — the public **measurement** (pure cold store read).

Consumes the versioned price lake via the ``SnapshotStore`` Protocol (injected) and
derives two objects that the product displays, **both point-in-time**:

- :class:`MarketView` — snapshot at ``as_of``: retained venues sorted + canonical index;
- :func:`price_curve` — the index series per model over time.

Edge boundary: this **only measures** ("who is cheapest, at what level"). The
**decision** ("rent now") is an injected signal, outside this module
(cf. ``signal_iface``). No rewriting of ``core/``: pure consumer.

The canonical index and anti look-ahead are **delegated** to
:func:`core.ingestion.compute_index.build_spot_index` (already tested); only the
per-venue reduction (for the "cheapest" *ranking*) is reimplemented here, since ``core`` does not
expose per-venue rates. → convergence handoff: promote a ``venue_rates`` helper into
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

#: Columns of the index curve returned by :func:`price_curve`.
CURVE_COLUMNS: list[str] = ["as_of", "index_price", "n_sources"]


@dataclass(frozen=True)
class MarketView:
    """Point-in-time snapshot of a GPU model: retained venues + canonical index.

    ``venues`` are already **filtered** (same outliers rejected as the index) and
    **sorted** by ascending price: ``cheapest`` is therefore the *credible* cheapest
    venue at ``as_of`` (an aberrant reading is never presented as the cheapest).
    """

    as_of: dt.datetime
    gpu_model: str
    venues: tuple[VenueRate, ...]
    index_price: float
    method: str

    def __post_init__(self) -> None:
        if not self.venues:
            raise ValueError("MarketView with no venue: illegal state (use read_market).")

    @property
    def cheapest(self) -> VenueRate:
        """Cheapest venue among the retained venues (``venues`` is sorted)."""
        return self.venues[0]

    @property
    def median_rate(self) -> float:
        """Median of the retained cross-venue rates ($/GPU·h)."""
        return statistics.median(v.rate for v in self.venues)


def _venue_rates(
    snapshots: Sequence[Snapshot],
    as_of: dt.datetime,
    gpu_model: str,
    config: IndexConfig,
) -> list[VenueRate]:
    """Reduces snapshots to one rate per venue (freshest cohort).

    Reuses the logic of :func:`build_spot_index` (staleness + point-in-time + hyperscaler
    exclusion + lease type) to expose the *per-venue* rates needed for the product
    ranking, which ``core`` does not return.
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
    """Builds the point-in-time :class:`MarketView` for ``gpu_model`` at ``as_of``.

    Parameters
    ----------
    store
        Snapshot source (real cold store or test double) — injected (DI).
    as_of
        Fix instant (UTC tz-aware). No later observation is used.
    gpu_model
        Aggregated model (e.g. ``"H100"``).
    config
        Aggregation config (estimator + filter + staleness). Default: market standard.

    Returns
    -------
    MarketView
        Retained venues sorted + canonical index.

    Raises
    ------
    InsufficientDataError
        If no fresh venue allows a fix to be computed (propagated from ``build_spot_index``).
    """
    as_of = ensure_utc(as_of)
    snapshots = store.load()
    # Canonical index + validation (no carry-forward, anti look-ahead) delegated to core.
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
    """Series of the canonical index for ``gpu_model`` at ``timestamps`` (point-in-time).

    Each point is computed by :func:`build_spot_index` on only the observations
    ``<= t``: the curve is anti look-ahead by construction. An instant with insufficient
    data yields ``index_price = NaN`` and ``n_sources = 0`` (graceful degradation, no
    carry-forward).

    Returns
    -------
    pandas.DataFrame
        Columns :data:`CURVE_COLUMNS` (``as_of``, ``index_price``, ``n_sources``).
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
