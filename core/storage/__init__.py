"""``core.storage`` — couche de stockage du labo (cold store + abstractions).

Pose la **couche d'abstraction** (Protocols) avant tout backend concret, et implémente
le **cold store reproductible** Phase 0–1 de ``docs/storage-roadmap.md`` :

- :class:`~core.storage.protocols.PriceStore` (+ stubs ``TickStream`` / ``HotCache``) ;
- :class:`~core.storage.parquet_store.ParquetPriceStore` — lac Parquet partitionné ;
- :func:`~core.storage.duckdb_query.query` — SQL embarqué (DuckDB) sur le lac ;
- :func:`~core.storage.migrate.migrate_csv_snapshots` — bascule CSV → Parquet.
"""

from __future__ import annotations

from core.storage.converters import frame_to_snapshots, snapshots_to_frame
from core.storage.duckdb_query import query
from core.storage.migrate import migrate_csv_snapshots
from core.storage.parquet_store import ParquetPriceStore
from core.storage.protocols import HotCache, PriceStore, TickStream
from core.storage.snapshot_store import ParquetSnapshotStore

__all__ = [
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
