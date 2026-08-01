"""GPU price collector — accumulates compute history day after day.

GPU rental price history does NOT exist retroactively: marketplaces only expose the
current price. We therefore build it by regularly taking a snapshot of the live price
and timestamping it. Schedule this script via cron (e.g. every hour).

**Dual write (Phase 0 transition)**: each reading is persisted to two backends.

- **CSV** via :class:`~core.ingestion.snapshot_store.CsvSnapshotStore` — unchanged, read by
  the P04 index until convergence repoints it at the Parquet store.
- **Parquet** via :class:`~core.storage.parquet_store.ParquetPriceStore` — the new cold
  store versioned as plain git, columnar/typed, which **preserves the distribution** of
  offers (whereas the CSV dedup on ``(t, source, model, lease)`` collapses it). See the
  "fix distribution" convergence handoff.

Both writes are **idempotent**: re-running the collector does not create duplicates.
The actual live reading comes from :func:`core.ingestion.gpu_market.fetch_live_gpu_prices`
(Vast.ai / RunPod; keys via ``.env``).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Sequence

from core.ingestion.gpu_market import fetch_live_gpu_prices
from core.ingestion.protocols import Snapshot
from core.ingestion.snapshot_store import CsvSnapshotStore
from core.storage import ParquetPriceStore, snapshots_to_frame

logger = logging.getLogger(__name__)

SNAPSHOT_DIR = Path(__file__).resolve().parents[2] / "data" / "snapshots"


def snapshot(
    csv_store: CsvSnapshotStore | None = None,
    parquet_store: ParquetPriceStore | None = None,
    *,
    fetch: Callable[[], Sequence[Snapshot]] = fetch_live_gpu_prices,
) -> tuple[Path, int]:
    """Take a live price reading and persist it twice (CSV P04 + Parquet cold store).

    Parameters
    ----------
    csv_store
        CSV store (P04). Defaults to ``data/snapshots/``.
    parquet_store
        Parquet cold store. Defaults to ``data/snapshots/`` (coexists with the CSVs).
    fetch
        Source of the readings (injectable for tests). Defaults to the live marketplace.

    Returns
    -------
    tuple[pathlib.Path, int]
        The CSV file written and the number of **new** rows added to the Parquet lake.
    """
    csv_store = csv_store or CsvSnapshotStore(SNAPSHOT_DIR)
    parquet_store = parquet_store or ParquetPriceStore(SNAPSHOT_DIR)

    rows = list(fetch())
    csv_path = csv_store.append(rows)
    written = parquet_store.write(snapshots_to_frame(rows))

    logger.info(
        "Snapshot collected: %d reading(s) -> CSV %s; %d new row(s) -> Parquet %s",
        len(rows),
        csv_path,
        written,
        parquet_store.root,
    )
    return csv_path, written


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    snapshot()
