"""Shared fixtures for P03 tests (volatility + term structure).

Makes the project code (under ``src/``) importable as top-level modules
(``vol``, ``term_structure``, ``signal``, ``spot_series``), following the same pattern as
P04's ``conftest.py``. Fixtures are **deterministic**: no hidden randomness.
"""

from __future__ import annotations

import datetime as dt
import math
import sys
from pathlib import Path

import numpy as np
import pytest

# Makes the project modules (under src/) importable in the tests.
_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

AS_OF = dt.datetime(2026, 6, 21, 0, 30, tzinfo=dt.timezone.utc)

# Reference amplitude of the alternating returns: known analytical per-period vol.
KNOWN_RETURN_AMPLITUDE = 0.02


@pytest.fixture
def as_of() -> dt.datetime:
    return AS_OF


@pytest.fixture
def alternating_returns() -> np.ndarray:
    """Alternating ±a returns: population per-period standard deviation = a (known)."""
    a = KNOWN_RETURN_AMPLITUDE
    return np.array([a, -a] * 60, dtype=float)


@pytest.fixture
def contango_curve() -> tuple[np.ndarray, np.ndarray]:
    """Upward-sloping curve (forward > spot): expected slope > 0."""
    maturities = np.array([0.0, 7.0, 30.0, 90.0, 180.0, 360.0])
    prices = 2.0 + 0.001 * maturities  # strictly increasing
    return maturities, prices


@pytest.fixture
def backwardation_curve() -> tuple[np.ndarray, np.ndarray]:
    """Downward-sloping curve (forward < spot): expected slope < 0."""
    maturities = np.array([0.0, 7.0, 30.0, 90.0, 180.0, 360.0])
    prices = 2.0 - 0.001 * maturities  # strictly decreasing
    return maturities, prices


@pytest.fixture
def flat_curve() -> tuple[np.ndarray, np.ndarray]:
    """Flat curve: slope ~ 0 (below threshold), expected shape 'flat'."""
    maturities = np.array([0.0, 7.0, 30.0, 90.0, 180.0, 360.0])
    prices = np.full_like(maturities, 2.0)
    return maturities, prices


@pytest.fixture
def convex_curve() -> tuple[np.ndarray, np.ndarray]:
    """Convex curve (smile shape): expected curvature > 0 (positive butterfly)."""
    maturities = np.array([0.0, 30.0, 60.0])
    prices = np.array([2.10, 2.00, 2.10])  # dip in the middle -> convex
    return maturities, prices


def annualized(per_period_vol: float, periods_per_year: float = 365.0) -> float:
    """Annualizes a per-period vol (test helper, no hidden magic)."""
    return per_period_vol * math.sqrt(periods_per_year)
