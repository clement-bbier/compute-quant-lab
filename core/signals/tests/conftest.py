"""Deterministic fixtures for the ``core.signals`` tests.

Each signal producer is proven on known series (analytic or OU), with a fixed seed so the runs
are reproducible (rule ``quant-no-lookahead``). The producers are point-in-time: they only
consume the P08 ``GuardedView`` (data <= t).
"""

from __future__ import annotations

import numpy as np
import pytest

from core.backtest.protocols import FloatArray

#: Single seed for all randomness in the fixtures (reproducibility).
SEED: int = 42


def ou_series(n: int, *, theta: float = 0.08, sigma: float = 1.0, seed: int = SEED) -> FloatArray:
    """Stationary Ornstein-Uhlenbeck series (oscillation gives mean reversion something to do)."""
    rng = np.random.default_rng(seed)
    x = np.empty(n, dtype=np.float64)
    x[0] = 100.0
    for t in range(1, n):
        x[t] = x[t - 1] - theta * (x[t - 1] - 100.0) + sigma * rng.standard_normal()
    return x


@pytest.fixture
def prices() -> FloatArray:
    """Synthetic, strictly positive desk price series (OU around 100)."""
    return np.clip(ou_series(256), 1.0, None).astype(np.float64)
