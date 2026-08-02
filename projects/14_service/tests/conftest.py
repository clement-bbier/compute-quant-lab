"""Fixtures for WS tests — ``service_product`` product layer.

In-memory doubles (no Parquet I/O) and a calibrated snapshot set for known
results, following P04 conventions (default index = 2.15 $/GPU·h).
"""

from __future__ import annotations

import datetime as dt
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import pytest

from core.ingestion.protocols import Snapshot

# Makes the product modules (under src/) importable in tests (lab convention).
_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

#: Reference fix instant (daily fix 00:30 UTC, consistent with P04).
AS_OF = dt.datetime(2026, 6, 21, 0, 30, tzinfo=dt.timezone.utc)


def ago(hours: float) -> dt.datetime:
    """UTC timestamp ``hours`` hours before :data:`AS_OF`."""
    return AS_OF - dt.timedelta(hours=hours)


@dataclass
class FakeSnapshotStore:
    """Test double of the ``SnapshotStore`` Protocol (in-memory, no Parquet)."""

    rows: list[Snapshot] = field(default_factory=list)

    def append(self, rows: Iterable[Snapshot]) -> Path:
        self.rows.extend(rows)
        return Path(".")

    def load(self) -> list[Snapshot]:
        return list(self.rows)


def h100_snapshots() -> list[Snapshot]:
    """Calibrated H100 on_demand set: default index = 2.15 $/GPU·h (cf. P04).

    4 valid fresh venues + traps to exclude: outlier (MAD rejection), stale reading
    (> 24 h), hyperscaler (excluded), future reading (look-ahead), other GPU model.
    Ranking of the *retained* venues: vastai 2.00 < lambda 2.10 < runpod 2.20 < coreweave 2.30.
    """
    h = "H100"
    return [
        Snapshot(ago(1), "vastai", h, 2.00, availability=100, simulated=False),
        Snapshot(ago(2), "runpod", h, 2.20, availability=50, simulated=False),
        Snapshot(ago(0.5), "lambda", h, 2.10, availability=200, simulated=False),
        Snapshot(ago(3), "coreweave", h, 2.30, availability=10, simulated=False),
        Snapshot(
            ago(0.2), "scam", h, 0.05, availability=1, simulated=False
        ),  # outlier -> MAD rejection
        Snapshot(ago(30), "old", h, 1.50, availability=99, simulated=False),  # stale > 24 h
        Snapshot(
            ago(0.1), "aws", h, 5.00, availability=999, simulated=False
        ),  # excluded hyperscaler
        Snapshot(AS_OF + dt.timedelta(hours=1), "future", h, 9.99, simulated=False),  # look-ahead
        Snapshot(ago(1), "vastai", "A100", 1.00, simulated=False),  # other GPU
    ]


@pytest.fixture
def as_of() -> dt.datetime:
    return AS_OF


@pytest.fixture
def store() -> FakeSnapshotStore:
    return FakeSnapshotStore(h100_snapshots())


@pytest.fixture
def empty_store() -> FakeSnapshotStore:
    return FakeSnapshotStore([])
