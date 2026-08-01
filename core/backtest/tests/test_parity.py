"""Rust vs Python-oracle parity: the Rust loop must reproduce PnL bit-for-bit.

The Rust loop is the *fast path*, not a requirement: the engine falls back to the
Python oracle when the crate is not compiled. These tests compare the two, so they
are *skipped* while the crate is absent -- same policy as the P01 spread kernel
(``tests/test_pricer_parity.py``). Build it with ``maturin develop``.
"""

from __future__ import annotations

import numpy as np
import pytest

from core.backtest.reference_loop import accumulate as accumulate_py

try:
    import backtest_loop
except ImportError:  # pragma: no cover - depends on whether the crate is built
    backtest_loop = None  # type: ignore[assignment]

pytestmark = pytest.mark.skipif(
    backtest_loop is None, reason="Rust kernel not compiled (maturin develop)"
)


def _random_positions(n: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.choice([-1.0, 0.0, 1.0], size=n).astype(np.float64)


def test_rust_matches_python_oracle_bit_for_bit(mean_reverting_prices):
    prices = mean_reverting_prices
    positions = _random_positions(prices.shape[0], seed=7)

    returns_py, n_py = accumulate_py(positions, prices, fees_bps=10.0, slippage_bps=5.0)
    returns_rs, n_rs = backtest_loop.accumulate(positions, prices, 10.0, 5.0)

    # Bit-for-bit: identical float64 operation order on both sides.
    np.testing.assert_array_equal(returns_py, returns_rs)
    assert n_py == n_rs


def test_parity_holds_without_costs(mean_reverting_prices):
    prices = mean_reverting_prices
    positions = _random_positions(prices.shape[0], seed=21)

    returns_py, n_py = accumulate_py(positions, prices, fees_bps=0.0, slippage_bps=0.0)
    returns_rs, n_rs = backtest_loop.accumulate(positions, prices, 0.0, 0.0)

    np.testing.assert_array_equal(returns_py, returns_rs)
    assert n_py == n_rs
