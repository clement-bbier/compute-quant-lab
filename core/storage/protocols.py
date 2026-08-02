"""The lab's storage abstractions (DI / SOLID).

Projects depend on these **Protocols**, never on a concrete backend: changing backend =
a new implementation, zero changes for consumers (OCP). Same pattern as the P04 ingestion
sources. This layer is laid down *before* any specific backend so that migrating between
phases is painless (see ``docs/storage-roadmap.md`` section 2).

Three roles, one per roadmap phase:

- :class:`PriceStore` — historical, immutable, point-in-time **cold store** (Phase 0-1).
  Implemented here by :class:`~core.storage.parquet_store.ParquetPriceStore`.
- :class:`TickStream` — real-time tick feed (Phase 2, Redpanda). **Documented stub.**
- :class:`HotCache` — latest low-latency price/feature (Phase 4, Redis). **Stub.**

Only ``PriceStore`` has a concrete implementation: ``TickStream`` and ``HotCache`` pin
down the contract of the institutional phases without prejudging the backend
(anti-over-engineering).
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Iterator, Mapping, Protocol, runtime_checkable

import pandas as pd


@runtime_checkable
class PriceStore(Protocol):
    """Append-only, point-in-time cold store of compute/energy price readings.

    Minimal contract shared by Parquet (Phase 0) then Timescale (Phase 3): an idempotent
    writer and a point-in-time reader. Consumers (features, backtests, models) only ever
    see this protocol.
    """

    def write(self, frame: pd.DataFrame) -> int:
        """Persist ``frame`` (append-only, idempotent); returns the number of new rows."""
        ...

    def read(self, *, as_of: dt.datetime | None = None, source: str | None = None) -> pd.DataFrame:
        """Read the store back; ``as_of`` bounds point-in-time (``snapshotted_at <= as_of``)."""
        ...


@runtime_checkable
class TickStream(Protocol):
    """Real-time tick feed — **Phase 2 stub** (Redpanda / Kafka-compatible).

    Not implemented: streaming only makes sense once the decision to tick
    intraday has been made (see roadmap section 3 Phase 2, section 4
    anti-over-engineering). Present to pin down the contract so that cold/hot sinks can
    plug into it without a rewrite.
    """

    def produce(self, tick: Mapping[str, Any]) -> None:
        """Publish a tick on the topic (e.g. ``compute.prices``)."""
        ...

    def consume(self) -> Iterator[Mapping[str, Any]]:
        """Iterate the ticks to feed a sink (cold Parquet, hot Timescale, Redis)."""
        ...


@runtime_checkable
class HotCache(Protocol):
    """Low-latency serving cache — **Phase 4 stub** (Redis).

    Not implemented: to be switched on when a live consumer exists (live spark spread
    pricer, P09 inference, P10 desk, dashboard). Serves serving/monitoring, **never**
    reproducibility (which always reads the versioned cold store).
    """

    def set_latest(self, key: str, value: Mapping[str, Any]) -> None:
        """Store the latest price/feature for ``key``."""
        ...

    def get_latest(self, key: str) -> Mapping[str, Any] | None:
        """Return the latest price/feature for ``key`` (or ``None`` if absent)."""
        ...
