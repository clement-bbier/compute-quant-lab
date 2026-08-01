"""Compute spot index construction (point-in-time, configurable).

``build_spot_index`` aggregates multi-venue observations into a canonical $/GPU·h price,
driven by an injectable :class:`IndexConfig`. The ``DEFAULT_INDEX_CONFIG`` default mirrors
the standard set by the leading players (GPU Markets / Silicon Data, CME compute futures
settlement): 20 % trimmed mean + 2.5 MAD rejection, 24 h window **without carry-forward**,
exclusion of hyperscaler list prices, separation of lease types.

Point-in-time guarantees: only observations with ``snapshotted_at <= as_of`` enter the fix,
and no stale venue (older than the staleness window) is ever forward-filled.

Two concrete sources implement :class:`ComputeIndexSource`:

- :class:`MarketplaceProxySource` — real, PoC: reads the accumulated snapshots (Vast.ai/
  RunPod) through a :class:`SnapshotStore`.
- :class:`SiliconDataSource` — canonical source (SDH100RT index); documented token-gated
  stub, pluggable without touching the core (OCP).
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

# Hyperscaler list prices: reported elsewhere but excluded from the estimator (market standard).
HYPERSCALERS: frozenset[str] = frozenset({"aws", "gcp", "azure"})

#: Separator qualifying an aggregator-relayed venue, as ``"<aggregator>:<venue>"``
#: (e.g. ``"primeintellect:datacrunch"``). Set by the provider parsers.
AGGREGATOR_SEPARATOR = ":"


def split_source(source: str) -> tuple[str | None, str]:
    """Split a source id into ``(aggregator, venue)``.

    A direct venue has no aggregator: ``"datacrunch"`` -> ``(None, "datacrunch")``.
    An aggregator-relayed one names both: ``"primeintellect:datacrunch"`` ->
    ``("primeintellect", "datacrunch")``.
    """
    aggregator, separator, venue = source.partition(AGGREGATOR_SEPARATOR)
    if not separator:
        return None, source
    return aggregator, venue


def prefer_direct_venues(rates: Sequence[VenueRate]) -> list[VenueRate]:
    """Drop aggregator quotes for venues that are also connected directly.

    Prime Intellect relays other providers' inventory, so ``primeintellect:datacrunch``
    and the direct ``datacrunch`` venue describe the *same* underlying capacity. Letting
    both into the estimator double-counts that venue and silently overweights it
    (see ``providers/CONVERGENCE.md`` section W2.4).

    The direct quote wins: it is one hop closer to the source, so it carries neither
    the aggregator's markup nor its refresh lag. An aggregator quote is kept whenever
    the venue has no direct feed, since it is then the only observation of that venue.

    Parameters
    ----------
    rates
        Per-venue rates, direct and aggregator-relayed alike.

    Returns
    -------
    list of VenueRate
        Input order preserved, minus the redundant aggregator quotes.
    """
    direct = {r.source for r in rates if split_source(r.source)[0] is None}
    return [r for r in rates if (a := split_source(r.source))[0] is None or a[1] not in direct]


class InsufficientDataError(RuntimeError):
    """Raised when no fresh venue allows a fix to be computed (no carry-forward)."""


@dataclass(frozen=True)
class IndexConfig:
    """Injectable index-construction parameters (everything is configurable).

    The ``DEFAULT_INDEX_CONFIG`` defaults encode the market standard; P03/P05/P06 can swap
    estimator, filter, window, etc. without forking the core.
    """

    estimator: IndexEstimator
    outlier_filter: OutlierFilter
    staleness: dt.timedelta = dt.timedelta(hours=24)
    lease_type: str = "on_demand"
    excluded_sources: frozenset[str] = HYPERSCALERS
    min_sources: int = 1
    #: Apply the direct > aggregator preference (see :func:`prefer_direct_venues`).
    #: On by default: double-counting a venue is a pricing error, not a preference.
    prefer_direct: bool = True

    @property
    def method(self) -> str:
        """Auditable identifier of the config, recorded in ``SpotIndexPoint.method``.

        Describes the estimator + filter pair. The direct > aggregator preference
        (:attr:`prefer_direct`) is deliberately absent: it deduplicates venues upstream of
        the estimation without changing the aggregation method, and this label is a stable
        contract that downstream consumers depend on (P03/P04/P05/P06).
        """
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
    """Compute the canonical spot index for ``gpu_model`` at instant ``as_of``.

    Parameters
    ----------
    snapshots
        Raw observations (all sources/models mixed); filtered here.
    as_of
        Fix instant (UTC). No later observation is used (anti look-ahead).
    gpu_model
        Aggregated model (e.g. ``"H100"``).
    config
        Aggregation strategies and parameters. Default: market standard.

    Returns
    -------
    SpotIndexPoint
        Canonical price + audit metadata (method, venue count, oldest observation).

    Raises
    ------
    InsufficientDataError
        If no fresh venue survives the filters and the outlier rejection.
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

    # A venue weighs only once: we aggregate the DISTRIBUTION of its freshest cohort
    # (robust median) instead of keeping an arbitrary offer on a timestamp tie. The
    # INTER-venue aggregation remains the estimator's responsibility.
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
            f"No fresh venue for {gpu_model}/{config.lease_type} at {as_of.isoformat()} "
            f"(window {config.staleness}): no fix (no carry-forward)."
        )

    # Before any statistic is computed: a venue relayed by an aggregator AND connected
    # directly must weigh once, else it skews both the MAD spread and the trimmed mean.
    if config.prefer_direct:
        venue_rates = prefer_direct_venues(venue_rates)

    kept = config.outlier_filter.filter(venue_rates)
    if len(kept) < config.min_sources:
        raise InsufficientDataError(
            f"Venue count ({len(kept)}) must be >= min_sources ({config.min_sources}) after "
            f"outlier rejection for {gpu_model}/{config.lease_type} at {as_of.isoformat()}."
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
    """Real source (PoC): spot index derived from the accumulated marketplace snapshots.

    Vast.ai/RunPod prices are *real* data collected in-house; this source acts as a proxy
    for the canonical index until Silicon Data is wired in.
    """

    store: SnapshotStore

    def fetch(self, start: dt.datetime, end: dt.datetime) -> Sequence[Snapshot]:
        start, end = ensure_utc(start), ensure_utc(end)
        return [s for s in self.store.load() if start <= s.snapshotted_at <= end]


@dataclass(frozen=True)
class SiliconDataSource:
    """Canonical Silicon Data source (SDH100RT index) — documented token-gated stub.

    Real wiring pending the API spec and the ``SILICONDATA_API_TOKEN`` token. Present here
    to pin the contract (OCP): replacing ``fetch`` with the real HTTP call will be enough,
    with no change to ``build_spot_index`` nor to its consumers.
    """

    api_token: str | None = field(default=None)

    def __post_init__(self) -> None:
        if self.api_token is None:
            object.__setattr__(self, "api_token", os.environ.get("SILICONDATA_API_TOKEN"))

    def fetch(self, start: dt.datetime, end: dt.datetime) -> Sequence[Snapshot]:
        raise NotImplementedError(
            "Canonical Silicon Data source (SDH100RT) is not wired in. "
            "Requires SILICONDATA_API_TOKEN + an API endpoint; must return Snapshot rows "
            "with source='silicon_data'. See the convergence handoff (source registry)."
        )
