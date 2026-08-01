"""Deterministic fixtures of the P09 tests (directional ML ensemble).

Two families of synthetic datasets with *known* properties, which encode the
anti-overfitting discipline in the suite itself:

* ``predictable_dataset`` — the target depends on a linear combination of the features
  (+ noise): a correct model **must** recover it (accuracy > chance);
* ``noise_dataset`` — independent features and target: under OOS validation, an honest
  model **must not** show skill (accuracy close to 0.5). This is the trap that catches
  backtest illusion / data leakage.

Seed fixed everywhere -> reproducible (``quant-no-lookahead`` rule).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

#: Single seed for all the randomness of the fixtures (reproducibility).
SEED: int = 42


def _utc_index(n: int) -> pd.DatetimeIndex:
    """Tz-aware UTC hourly grid of ``n`` points (the lab's point-in-time requirement)."""
    return pd.date_range("2025-01-01", periods=n, freq="h", tz="UTC")


@pytest.fixture
def predictable_dataset() -> tuple[np.ndarray, np.ndarray]:
    """``(X, y)`` where ``y`` follows a logistic model of the features (learnable signal).

    ``logit = X @ w`` with a sparse ``w``, then ``y ~ Bernoulli(sigmoid(logit))``: the
    relationship is real but noisy, so a good classifier clearly beats chance without
    reaching 100%.
    """
    rng = np.random.default_rng(SEED)
    n, k = 800, 5
    x = rng.standard_normal((n, k))
    w = np.array([2.0, -1.5, 0.0, 0.0, 0.0])
    p = 1.0 / (1.0 + np.exp(-(x @ w)))
    y = (rng.random(n) < p).astype(np.float64)
    return x, y


@pytest.fixture
def noise_dataset() -> tuple[np.ndarray, np.ndarray]:
    """Independent ``(X, y)``: no learnable signal (anti-overfitting sanity check)."""
    rng = np.random.default_rng(SEED + 1)
    n, k = 800, 5
    x = rng.standard_normal((n, k))
    y = (rng.random(n) < 0.5).astype(np.float64)
    return x, y


@pytest.fixture
def spread_series() -> pd.Series:
    """Synthetic spread (bounded random walk) to test labels & PIT features."""
    rng = np.random.default_rng(SEED + 2)
    n = 400
    values = 2.0 + np.cumsum(rng.standard_normal(n) * 0.05)
    return pd.Series(values, index=_utc_index(n), name="spread")
