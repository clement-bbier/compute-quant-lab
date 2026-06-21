"""(e) Migration CSV → Parquet : toutes les lignes du CSV sont préservées dans le lac."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from core.ingestion.protocols import Snapshot
from core.ingestion.snapshot_store import CsvSnapshotStore
from core.storage import ParquetPriceStore
from core.storage.migrate import migrate_csv_snapshots
from core.storage.schema import PRICE

_ORIGIN = dt.datetime(2025, 1, 1, tzinfo=dt.timezone.utc)


def test_migrate_preserves_all_rows(tmp_path: Path) -> None:
    csv_dir = tmp_path / "csv"
    CsvSnapshotStore(csv_dir).append(
        [
            Snapshot(_ORIGIN, "vastai", "H100", 2.50, "on_demand", 8),
            Snapshot(_ORIGIN + dt.timedelta(hours=1), "vastai", "H100", 2.55, "on_demand", 8),
            Snapshot(_ORIGIN, "runpod", "H100", 2.20, "on_demand", 1),
        ]
    )
    store = ParquetPriceStore(tmp_path / "parquet")

    migrated = migrate_csv_snapshots(csv_dir, store)

    assert migrated == 3
    out = store.read()
    assert len(out) == 3
    assert sorted(out[PRICE].tolist()) == [2.20, 2.50, 2.55]


def test_migrate_is_idempotent(tmp_path: Path) -> None:
    csv_dir = tmp_path / "csv"
    CsvSnapshotStore(csv_dir).append([Snapshot(_ORIGIN, "vastai", "H100", 2.50, "on_demand", 8)])
    store = ParquetPriceStore(tmp_path / "parquet")

    migrate_csv_snapshots(csv_dir, store)
    again = migrate_csv_snapshots(csv_dir, store)

    assert again == 0
    assert len(store.read()) == 1


def test_migrate_empty_dir_is_noop(tmp_path: Path) -> None:
    store = ParquetPriceStore(tmp_path / "parquet")

    assert migrate_csv_snapshots(tmp_path / "empty", store) == 0
    assert store.read().empty
