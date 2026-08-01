"""Deterministic fixtures for the P02 tests (cointegration + mean reversion).

Synthetic series with *known* properties: we prove cointegration detection and
the mean-reversion signal on analytical cases **before** any real data.
Seed fixed everywhere -> reproducible (rule ``quant-no-lookahead``).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Makes the project's modules (under src/) importable in the tests, like P04.
_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

#: Single seed for all fixture randomness (reproducibility).
SEED: int = 42


def _utc_index(n: int) -> pd.DatetimeIndex:
    """Hourly UTC tz-aware grid of ``n`` points (the lab's point-in-time requirement)."""
    return pd.date_range("2025-01-01", periods=n, freq="h", tz="UTC")


def _ornstein_uhlenbeck(
    n: int,
    *,
    theta: float,
    sigma: float,
    rng: np.random.Generator,
    x0: float = 0.0,
    mu: float = 0.0,
) -> np.ndarray:
    """Discrete OU process ``x[t] = x[t-1] + theta·(mu - x[t-1]) + sigma·N(0,1)`` (stationary)."""
    x = np.empty(n, dtype=np.float64)
    x[0] = x0
    for t in range(1, n):
        x[t] = x[t - 1] + theta * (mu - x[t - 1]) + sigma * rng.standard_normal()
    return x


@pytest.fixture
def cointegrated_pair() -> tuple[pd.Series, pd.Series, float]:
    """*Known* cointegrated pair: ``y = α + β·x + u``, x an I(1) random walk, u stationary (OU).

    The residual ``y - β·x`` is stationary -> true cointegration. Returns ``(y, x, β)``.
    """
    rng = np.random.default_rng(SEED)
    n = 600
    x = 100.0 + np.cumsum(rng.standard_normal(n))  # I(1) random walk
    u = _ornstein_uhlenbeck(n, theta=0.10, sigma=1.0, rng=rng)  # stationary residual
    alpha, beta = 5.0, 1.5
    y = alpha + beta * x + u
    idx = _utc_index(n)
    return pd.Series(y, index=idx, name="y"), pd.Series(x, index=idx, name="x"), beta


#: Seed for a *clearly* non-cointegrated realization (Engle-Granger p≈0.96 on 600 points).
#: Under H0 "no cointegration", the p-value is ~uniform: ~10% of independent pairs
#: appear borderline (spurious regression). We keep a clear-cut case for a non-flaky test.
_NON_COINTEGRATED_SEED: int = 5


@pytest.fixture
def independent_random_walks() -> tuple[pd.Series, pd.Series]:
    """Two *independent* random walks -> not cointegrated (anti-spurious trap)."""
    rng = np.random.default_rng(_NON_COINTEGRATED_SEED)
    n = 600
    x = 100.0 + np.cumsum(rng.standard_normal(n))
    y = 50.0 + np.cumsum(rng.standard_normal(n))
    idx = _utc_index(n)
    return pd.Series(y, index=idx, name="y"), pd.Series(x, index=idx, name="x")


@pytest.fixture
def ou_spread_known_half_life() -> tuple[pd.Series, float]:
    """OU spread with a *known* half-life: ``Δs = -λ·s + ε`` -> half-life = ln(2)/λ."""
    rng = np.random.default_rng(SEED + 2)
    n = 3000
    lam = 0.10
    s = _ornstein_uhlenbeck(n, theta=lam, sigma=0.5, rng=rng)
    return pd.Series(s, index=_utc_index(n), name="spread"), float(np.log(2.0) / lam)


@pytest.fixture
def mean_reverting_spread() -> pd.Series:
    """*Positive* spread (OU around 2.0 $/GPU·h) for a realistic deterministic backtest."""
    rng = np.random.default_rng(SEED + 3)
    n = 512
    s = _ornstein_uhlenbeck(n, theta=0.05, sigma=0.05, rng=rng, x0=2.0, mu=2.0)
    return pd.Series(s, index=_utc_index(n), name="spread")
