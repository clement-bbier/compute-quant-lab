"""Phase-2 kernel selection: Rust is the fast path, the Python oracle the fallback.

Pins the contract that ``import core.backtest`` never requires a Rust build. The
engine used to import ``backtest_loop`` unconditionally, so the whole package was
unimportable on any machine that had not run ``maturin develop``.
"""

from __future__ import annotations

import numpy as np

from core.backtest import engine
from core.backtest.reference_loop import accumulate as accumulate_py


def test_engine_exposes_a_usable_kernel() -> None:
    """Whatever the build state, a callable accumulator is wired up."""
    assert callable(engine.accumulate)
    assert isinstance(engine.USING_RUST_KERNEL, bool)


def test_kernel_choice_matches_crate_availability() -> None:
    """``USING_RUST_KERNEL`` tells the truth about which implementation is bound."""
    try:
        import backtest_loop
    except ImportError:
        assert engine.USING_RUST_KERNEL is False
        assert engine.accumulate is accumulate_py
    else:
        assert engine.USING_RUST_KERNEL is True
        assert engine.accumulate is backtest_loop.accumulate


def test_active_kernel_matches_the_oracle(mean_reverting_prices) -> None:
    """The bound kernel agrees with the reference oracle bit-for-bit.

    Trivially true on the fallback path; on the fast path this is the same parity
    property that ``test_parity`` asserts, checked through the engine's own binding.
    """
    prices = mean_reverting_prices
    rng = np.random.default_rng(11)
    positions = rng.choice([-1.0, 0.0, 1.0], size=prices.shape[0]).astype(np.float64)

    returns, n_trades = engine.accumulate(positions, prices, 10.0, 5.0)
    expected_returns, expected_trades = accumulate_py(positions, prices, 10.0, 5.0)

    np.testing.assert_array_equal(returns, expected_returns)
    assert n_trades == expected_trades
