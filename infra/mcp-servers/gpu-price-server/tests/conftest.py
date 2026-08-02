"""Fixtures for the gpu-price MCP server: a Parquet cold store seeded with known data."""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pytest

# server.py and service.py live in the parent folder (run outside the package).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.ingestion.protocols import Snapshot  # noqa: E402
from core.storage import ParquetPriceStore, snapshots_to_frame  # noqa: E402

UTC = dt.timezone.utc
T0 = dt.datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
T1 = dt.datetime(2026, 6, 2, 12, 0, tzinfo=UTC)


@pytest.fixture
def snapshots() -> list[Snapshot]:
    """7 deterministic readings: 2 sources, 3 models, 2 instants; vastai has 2 H100 offers at T1."""
    return [
        Snapshot(T0, "vastai", "H100", 2.00, "on_demand", 5, simulated=False),
        Snapshot(T0, "runpod", "H100", 2.20, "on_demand", 3, simulated=False),
        Snapshot(T1, "vastai", "H100", 1.80, "on_demand", 4, simulated=False),
        Snapshot(T1, "vastai", "H100", 1.90, "on_demand", 2, simulated=False),
        Snapshot(T1, "runpod", "H100", 2.10, "on_demand", 1, simulated=False),
        Snapshot(T0, "vastai", "A100", 1.00, "on_demand", 10, simulated=False),
        Snapshot(T1, "vastai", "B200", 3.50, "on_demand", 1, simulated=False),
    ]


@pytest.fixture
def store(tmp_path: Path, snapshots: list[Snapshot]) -> ParquetPriceStore:
    """Temporary Parquet cold store seeded with `snapshots`."""
    lake = ParquetPriceStore(tmp_path / "lake")
    lake.write(snapshots_to_frame(snapshots))
    return lake
