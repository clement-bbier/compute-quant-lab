"""Protocols and types of the compute leg (ingestion).

Defines the injectable abstractions (DI / SOLID) of the compute ingestion subsystem and the
immutable data types that flow between the layers: index source -> snapshot store ->
aggregation -> clean spot index.

Two families of abstractions, all interchangeable through injection (OCP):

- **sources** (:class:`ComputeIndexSource`): where the prices come from (Silicon Data, a
  marketplace proxy, etc.);
- **aggregation** (:class:`OutlierFilter`, :class:`IndexEstimator`): how heterogeneous
  per-venue prices become one canonical price. Adding a method means a new implementation,
  without touching the ``build_spot_index`` core.

Every timestamp is UTC timezone-aware (data integrity rule): the dataclasses normalise on
construction and reject a naive datetime, so an illegal state (an ambiguous instant) cannot
be represented.

Price unit: USD per GPU-hour ($/GPU·h), per the P04 framing.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Protocol, Sequence, runtime_checkable


def ensure_utc(ts: dt.datetime) -> dt.datetime:
    """Convert ``ts`` to UTC; raise if ``ts`` is naive.

    Parameters
    ----------
    ts
        Timezone-aware timestamp. A naive datetime is rejected to avoid any point-in-time
        ambiguity.

    Returns
    -------
    datetime.datetime
        The same instant, expressed in UTC.

    Raises
    ------
    ValueError
        If ``ts`` carries no timezone (naive datetime).
    """
    if ts.tzinfo is None:
        raise ValueError("ts must be tz-aware (UTC): a naive datetime is forbidden.")
    return ts.astimezone(dt.timezone.utc)


@dataclass(frozen=True)
class Snapshot:
    """Price observation from a compute source at a given instant (raw unit).

    Append-only unit stored and deduplicated by the :class:`SnapshotStore`. The price is in
    USD per GPU-hour. ``lease_type`` distinguishes on-demand / spot / reserved: different
    lease types are never aggregated together (Silicon Data standard).

    The optional descriptive fields (``region``, ``gpu_memory_gb``, ``vcpu``, ``ram_gb``,
    ``disk_gb``, ``provider_detail``) enrich the observation when the venue's API exposes
    them. They do NOT take part in ``dedup_key``: idempotence stays on (instant, source,
    model, lease) -- hardware metadata never breaks point-in-time deduplication.
    """

    snapshotted_at: dt.datetime
    source: str
    gpu_model: str
    price_usd_per_hour: float
    lease_type: str = "on_demand"
    availability: int = 0
    # -- optional descriptive fields (backward compatible: all existing code compiles) --
    region: str | None = None
    gpu_memory_gb: float | None = None
    vcpu: int | None = None
    ram_gb: float | None = None
    disk_gb: float | None = None
    provider_detail: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshotted_at", ensure_utc(self.snapshotted_at))

    @property
    def dedup_key(self) -> tuple[str, str, str, str]:
        """Natural idempotence key: (ISO instant, source, GPU model, lease type)."""
        return (self.snapshotted_at.isoformat(), self.source, self.gpu_model, self.lease_type)


@dataclass(frozen=True)
class VenueRate:
    """Representative rate of one venue (marketplace) entering the aggregation.

    Produced by reducing, per source, the fresh snapshots down to the most recent one. This
    is the unit the aggregation strategies see (:class:`OutlierFilter`,
    :class:`IndexEstimator`).
    """

    source: str
    rate: float
    availability: int
    snapshotted_at: dt.datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshotted_at", ensure_utc(self.snapshotted_at))


@dataclass(frozen=True)
class SpotIndexPoint:
    """Canonical value of the compute spot index for one model at one instant.

    Produced by ``build_spot_index`` by aggregating several venues. ``method`` records the
    aggregation config (estimator + filter) and ``oldest_obs_at`` the age of the oldest
    observation kept: together they make every point **auditable and replayable**.
    """

    as_of: dt.datetime
    gpu_model: str
    lease_type: str
    price_usd_per_hour: float
    n_sources: int
    method: str
    oldest_obs_at: dt.datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "as_of", ensure_utc(self.as_of))
        object.__setattr__(self, "oldest_obs_at", ensure_utc(self.oldest_obs_at))


@runtime_checkable
class ComputeIndexSource(Protocol):
    """Compute price source (Silicon Data, marketplace proxy, etc.).

    Injection abstraction: the index aggregates sources through this protocol, so adding a
    marketplace means a new implementation without touching the core (OCP).
    """

    def fetch(self, start: dt.datetime, end: dt.datetime) -> Sequence[Snapshot]:
        """Return the observations available in the ``[start, end]`` window (UTC)."""
        ...


@runtime_checkable
class SnapshotStore(Protocol):
    """Append-only, idempotent storage of compute price snapshots."""

    def append(self, rows: Iterable[Snapshot]) -> Path:
        """Append ``rows``, deduplicating by natural key; return the file written."""
        ...

    def load(self) -> list[Snapshot]:
        """Reload every stored snapshot (order not guaranteed)."""
        ...


@runtime_checkable
class OutlierFilter(Protocol):
    """Strategy for rejecting aberrant rates before aggregation (interchangeable)."""

    @property
    def name(self) -> str:
        """Short identifier recorded in ``SpotIndexPoint.method`` (e.g. ``mad2.5``)."""
        ...

    def filter(self, rates: Sequence[VenueRate]) -> list[VenueRate]:
        """Return the subset of rates kept (outliers removed)."""
        ...


@runtime_checkable
class IndexEstimator(Protocol):
    """Strategy aggregating per-venue rates into a canonical price (interchangeable)."""

    @property
    def name(self) -> str:
        """Short identifier recorded in ``SpotIndexPoint.method`` (e.g. ``trimmed_mean20``)."""
        ...

    def estimate(self, rates: Sequence[VenueRate]) -> float:
        """Aggregate the (non-empty) ``rates`` into a single $/GPU·h price."""
        ...
