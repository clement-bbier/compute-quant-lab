"""*Deterministic* synthetic fixtures for the backtest engine.

Source-agnostic (see P08): the engine is proven on known series with analytic
answers before any external data. Fixed seed, hence reproducible.
"""

from __future__ import annotations

import numpy as np
import pytest

#: Single seed for all randomness in the fixtures (reproducibility).
SEED: int = 42


@pytest.fixture
def mean_reverting_prices() -> np.ndarray:
    """Deterministic mean-reverting price series (discrete OU process).

    Acts as a "known long history" for Rust/Python parity and determinism.
    """
    rng = np.random.default_rng(SEED)
    n = 512
    theta, mu, sigma = 0.05, 100.0, 1.0
    prices = np.empty(n, dtype=np.float64)
    prices[0] = mu
    for t in range(1, n):
        shock = sigma * rng.standard_normal()
        prices[t] = prices[t - 1] + theta * (mu - prices[t - 1]) + shock
    return prices


@pytest.fixture
def known_drawdown_equity() -> np.ndarray:
    """Equity curve with a known analytic drawdown.

    Peak at 2.0 then trough at 1.5 ⇒ max drawdown = (1.5 - 2.0) / 2.0 = -25 %.
    """
    return np.array([1.0, 2.0, 1.5, 3.0], dtype=np.float64)


@pytest.fixture
def flat_prices() -> np.ndarray:
    """Prices held flat at 100 — isolates cost accounting from market PnL."""
    return np.full(8, 100.0, dtype=np.float64)
