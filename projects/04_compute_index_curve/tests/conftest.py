"""Shared fixtures for P04 tests (spot index + forward curve)."""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pytest

from core.ingestion.protocols import Snapshot

# Makes the project package `forward` (under src/) importable in the tests.
_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# Reference fix instant (analogous to GPU Markets' daily 00:30 UTC fix).
AS_OF = dt.datetime(2026, 6, 21, 0, 30, tzinfo=dt.timezone.utc)


def _ago(hours: float) -> dt.datetime:
    """UTC timestamp located ``hours`` hours before ``AS_OF``."""
    return AS_OF - dt.timedelta(hours=hours)


@pytest.fixture
def as_of() -> dt.datetime:
    return AS_OF


@pytest.fixture
def index_snapshots() -> list[Snapshot]:
    """H100 on_demand dataset calibrated for a known result.

    4 valid venues (vastai/runpod/lambda/coreweave), plus traps that must
    all be discarded: an outlier (rejected by MAD), a stale reading (> 24h),
    a hyperscaler (excluded from the estimator), a future reading (look-ahead) and another
    GPU model. Expected index (default config) = 2.15 $/GPU·h.
    """
    h = "H100"
    return [
        Snapshot(_ago(1), "vastai", h, 2.00, availability=100, simulated=False),
        Snapshot(_ago(2), "runpod", h, 2.20, availability=50, simulated=False),
        Snapshot(_ago(0.5), "lambda", h, 2.10, availability=200, simulated=False),
        Snapshot(
            _ago(3), "coreweave", h, 2.30, availability=10, simulated=False
        ),  # oldest retained
        Snapshot(_ago(0.2), "scam", h, 0.05, availability=1, simulated=False),  # outlier -> MAD
        Snapshot(_ago(30), "old", h, 1.50, availability=99, simulated=False),  # stale > 24h
        Snapshot(
            _ago(0.1), "aws", h, 5.00, availability=999, simulated=False
        ),  # hyperscaler excluded
        Snapshot(AS_OF + dt.timedelta(hours=1), "future", h, 9.99, simulated=False),  # look-ahead
        Snapshot(_ago(1), "vastai", "A100", 1.00, simulated=False),  # other GPU
    ]
