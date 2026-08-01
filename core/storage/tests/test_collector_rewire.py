"""Collector rewire: dual CSV + Parquet writing, idempotent, network-free.

The network ``fetch`` is injected by an in-memory factory: *persistence* is tested, not
marketplace I/O (covered elsewhere). Highlights the distribution fix: the Parquet lake
keeps the distinct offers that the CSV (P04 dedup) overwrites.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from core.ingestion.protocols import Snapshot
from core.ingestion.snapshot_store import CsvSnapshotStore
from core.storage import ParquetPriceStore
from infra.collectors.gpu_price_snapshot import snapshot

_ORIGIN = dt.datetime(2025, 1, 1, tzinfo=dt.timezone.utc)


def _rows() -> list[Snapshot]:
    return [
        Snapshot(_ORIGIN, "vastai", "H100", 2.50, "on_demand", 8),
        Snapshot(_ORIGIN, "vastai", "H100", 2.65, "on_demand", 4),  # distinct offer, same CSV key
        Snapshot(_ORIGIN, "runpod", "H100", 2.20, "on_demand", 1),
    ]


def test_snapshot_dual_writes_csv_and_parquet(tmp_path: Path) -> None:
    csv_store = CsvSnapshotStore(tmp_path / "snap")
    parquet_store = ParquetPriceStore(tmp_path / "snap")

    _, written = snapshot(csv_store, parquet_store, fetch=_rows)

    assert written == 3  # Parquet keeps the distribution
    assert len(parquet_store.read()) == 3
    assert len(csv_store.load()) >= 1  # the CSV also receives the readings (P04 unchanged)


def test_snapshot_parquet_is_idempotent(tmp_path: Path) -> None:
    csv_store = CsvSnapshotStore(tmp_path / "snap")
    parquet_store = ParquetPriceStore(tmp_path / "snap")

    snapshot(csv_store, parquet_store, fetch=_rows)
    _, written = snapshot(csv_store, parquet_store, fetch=_rows)

    assert written == 0
    assert len(parquet_store.read()) == 3
