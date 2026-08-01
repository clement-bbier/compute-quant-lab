"""``core.storage`` — the lab's storage layer (cold store + abstractions).

Lays down the **abstraction layer** (Protocols) before any concrete backend, and
implements the **reproducible cold store** of Phase 0-1 of ``docs/storage-roadmap.md``:

- :class:`~core.storage.protocols.PriceStore` (+ ``TickStream`` / ``HotCache`` stubs);
- :class:`~core.storage.parquet_store.ParquetPriceStore` — partitioned Parquet lake;
- :func:`~core.storage.duckdb_query.query` — embedded SQL (DuckDB) over the lake;
- :func:`~core.storage.migrate.migrate_csv_snapshots` — CSV to Parquet switchover.
"""

from __future__ import annotations

from core.storage.converters import frame_to_snapshots, snapshots_to_frame
from core.storage.duckdb_query import query
from core.storage.energy_store import EnergyColdStore
from core.storage.migrate import migrate_csv_snapshots
from core.storage.parquet_store import ParquetPriceStore
from core.storage.protocols import HotCache, PriceStore, TickStream
from core.storage.snapshot_store import ParquetSnapshotStore

__all__ = [
    "EnergyColdStore",
    "ParquetPriceStore",
    "ParquetSnapshotStore",
    "PriceStore",
    "TickStream",
    "HotCache",
    "query",
    "migrate_csv_snapshots",
    "snapshots_to_frame",
    "frame_to_snapshots",
]
