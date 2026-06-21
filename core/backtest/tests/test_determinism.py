"""Déterminisme : mêmes entrées → mêmes sorties au bit (reproductibilité)."""

from __future__ import annotations

import backtest_loop
import numpy as np


def test_rust_loop_is_deterministic(mean_reverting_prices):
    prices = mean_reverting_prices
    rng = np.random.default_rng(99)
    positions = rng.choice([-1.0, 0.0, 1.0], size=prices.shape[0]).astype(np.float64)

    r1, n1 = backtest_loop.accumulate(positions, prices, 10.0, 5.0)
    r2, n2 = backtest_loop.accumulate(positions, prices, 10.0, 5.0)

    np.testing.assert_array_equal(r1, r2)
    assert n1 == n2
