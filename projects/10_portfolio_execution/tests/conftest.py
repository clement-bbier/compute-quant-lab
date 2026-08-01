"""Deterministic fixtures for the P10 tests (desk: portfolio + execution).

We prove the weighting, execution costs, anti look-ahead, and net PnL on
analytical cases **before** wiring in the real signals (P02/P06/P09, at convergence).
Fixed seed everywhere → reproducible (rule ``quant-no-lookahead``).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

# Makes the project modules (under src/) importable in tests, like P02/P04.
_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

#: Single seed for all fixture randomness (reproducibility).
SEED: int = 42


@pytest.fixture
def desk_prices() -> np.ndarray:
    """Synthetic *positive* desk price series (bounded random walk), float64.

    Serves as the desk's single underlying: mocked signals are applied to it via P08's
    ``GuardedView``. Strictly simulated.
    """
    rng = np.random.default_rng(SEED)
    n = 256
    prices = 100.0 + np.cumsum(rng.standard_normal(n) * 0.5)
    return np.clip(prices, 1.0, None).astype(np.float64)
