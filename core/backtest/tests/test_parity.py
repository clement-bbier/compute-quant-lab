"""Parité Rust ↔ oracle Python : la boucle Rust doit reproduire le PnL bit-à-bit.

La boucle Rust est OBLIGATOIRE (pas de fallback) : on importe `backtest_loop`
directement — si le crate n'est pas compilé, ces tests échouent (choix assumé).
"""

from __future__ import annotations

import backtest_loop
import numpy as np

from core.backtest.reference_loop import accumulate as accumulate_py


def _random_positions(n: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.choice([-1.0, 0.0, 1.0], size=n).astype(np.float64)


def test_rust_matches_python_oracle_bit_for_bit(mean_reverting_prices):
    prices = mean_reverting_prices
    positions = _random_positions(prices.shape[0], seed=7)

    returns_py, n_py = accumulate_py(positions, prices, fees_bps=10.0, slippage_bps=5.0)
    returns_rs, n_rs = backtest_loop.accumulate(positions, prices, 10.0, 5.0)

    # Bit-à-bit : même ordre d'opérations float64 des deux côtés.
    np.testing.assert_array_equal(returns_py, returns_rs)
    assert n_py == n_rs


def test_parity_holds_without_costs(mean_reverting_prices):
    prices = mean_reverting_prices
    positions = _random_positions(prices.shape[0], seed=21)

    returns_py, n_py = accumulate_py(positions, prices, fees_bps=0.0, slippage_bps=0.0)
    returns_rs, n_rs = backtest_loop.accumulate(positions, prices, 0.0, 0.0)

    np.testing.assert_array_equal(returns_py, returns_rs)
    assert n_py == n_rs
