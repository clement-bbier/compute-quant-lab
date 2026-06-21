"""Rewire du collecteur : double écriture CSV + Parquet, idempotente, sans réseau.

Le ``fetch`` réseau est injecté par une factory en mémoire : on teste la *persistance*,
pas l'I/O marketplace (couverte ailleurs). Met en évidence le fix distribution : le lac
Parquet conserve les offres distinctes que le CSV (dédup P04) écrase.
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
        Snapshot(_ORIGIN, "vastai", "H100", 2.65, "on_demand", 4),  # offre distincte, même clé CSV
        Snapshot(_ORIGIN, "runpod", "H100", 2.20, "on_demand", 1),
    ]


def test_snapshot_dual_writes_csv_and_parquet(tmp_path: Path) -> None:
    csv_store = CsvSnapshotStore(tmp_path / "snap")
    parquet_store = ParquetPriceStore(tmp_path / "snap")

    _, written = snapshot(csv_store, parquet_store, fetch=_rows)

    assert written == 3  # Parquet conserve la distribution
    assert len(parquet_store.read()) == 3
    assert len(csv_store.load()) >= 1  # le CSV reçoit aussi les relevés (P04 inchangé)


def test_snapshot_parquet_is_idempotent(tmp_path: Path) -> None:
    csv_store = CsvSnapshotStore(tmp_path / "snap")
    parquet_store = ParquetPriceStore(tmp_path / "snap")

    snapshot(csv_store, parquet_store, fetch=_rows)
    _, written = snapshot(csv_store, parquet_store, fetch=_rows)

    assert written == 0
    assert len(parquet_store.read()) == 3
