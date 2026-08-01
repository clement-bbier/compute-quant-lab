"""Determinism: identical inputs give bit-identical outputs (reproducibility)."""

from __future__ import annotations

import numpy as np
import pytest

from core.backtest.engine import accumulate

try:
    import backtest_loop
except ImportError:  # pragma: no cover - depends on whether the crate is built
    backtest_loop = None  # type: ignore[assignment]


def _positions(n: int, seed: int = 99) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.choice([-1.0, 0.0, 1.0], size=n).astype(np.float64)


@pytest.mark.skipif(backtest_loop is None, reason="Rust kernel not compiled (maturin develop)")
def test_rust_loop_is_deterministic(mean_reverting_prices):
    prices = mean_reverting_prices
    positions = _positions(prices.shape[0])

    r1, n1 = backtest_loop.accumulate(positions, prices, 10.0, 5.0)
    r2, n2 = backtest_loop.accumulate(positions, prices, 10.0, 5.0)

    np.testing.assert_array_equal(r1, r2)
    assert n1 == n2


def test_active_kernel_is_deterministic(mean_reverting_prices):
    """Holds for whichever phase-2 kernel the engine selected (Rust or oracle)."""
    prices = mean_reverting_prices
    positions = _positions(prices.shape[0])

    r1, n1 = accumulate(positions, prices, 10.0, 5.0)
    r2, n2 = accumulate(positions, prices, 10.0, 5.0)

    np.testing.assert_array_equal(r1, r2)
    assert n1 == n2
