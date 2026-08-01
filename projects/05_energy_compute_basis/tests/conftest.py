"""Shared fixtures for P05 tests (inter-region energy ↔ compute basis).

All series are deterministic with known values (computable by hand), UTC tz-aware
index. No network access: real I/O lives in ``src/data.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

# Makes project modules (under src/) importable in tests: `from basis import ...`.
_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


@pytest.fixture
def utc_index() -> pd.DatetimeIndex:
    """UTC tz-aware hourly grid (4 points) — left edge 2026-01-01."""
    return pd.date_range("2026-01-01", periods=4, freq="h", tz="UTC")


@pytest.fixture
def energy_two_regions(utc_index: pd.DatetimeIndex) -> pd.DataFrame:
    """€/MWh electricity prices for FR and DE: FR alternately below and above DE."""
    return pd.DataFrame(
        {
            "FR": [100.0, 120.0, 80.0, 110.0],
            "DE": [90.0, 130.0, 95.0, 100.0],
        },
        index=utc_index,
    )


@pytest.fixture
def compute_global(utc_index: pd.DatetimeIndex) -> pd.DataFrame:
    """GLOBAL compute index ($/GPU·h): a single column, identical across all regions."""
    return pd.DataFrame({"H100": [2.00, 2.00, 2.00, 2.00]}, index=utc_index)
