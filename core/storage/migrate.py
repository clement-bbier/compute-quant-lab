"""Historical cold store migration: monthly CSV files (P04) to the Parquet lake (Phase 0).

Switches the proprietary ``data/snapshots/gpu_prices_*.csv`` series over to the
partitioned Parquet lake, **losslessly**: reading reuses the P04 ``CsvSnapshotStore`` (so
the CSV format remains its source of truth), then ``PriceStore.write`` (idempotent)
absorbs the rows. Replaying the migration is a no-op (no duplicates).
"""

from __future__ import annotations

from pathlib import Path

from core.ingestion.snapshot_store import CsvSnapshotStore
from core.storage.converters import snapshots_to_frame
from core.storage.protocols import PriceStore


def migrate_csv_snapshots(csv_dir: Path | str, store: PriceStore) -> int:
    """Migrate the CSV snapshots of ``csv_dir`` to ``store``; returns the number of new rows.

    Parameters
    ----------
    csv_dir
        Directory of the ``gpu_prices_YYYYMM.csv`` files (read via ``CsvSnapshotStore``).
    store
        Destination cold store (typically a ``ParquetPriceStore``).

    Returns
    -------
    int
        Number of rows actually written (0 if already migrated or the directory is empty).
    """
    snapshots = CsvSnapshotStore(Path(csv_dir)).load()
    return store.write(snapshots_to_frame(snapshots))
