"""Tests for the demo fixtures: the strategy behind P08's committed headline metrics.

``ZScoreMeanReversion`` and ``synthetic_prices`` back the reproducible demo run
(Sharpe/PnL numbers in results/SYNTHESIS.md) but have no dedicated coverage in
``core/backtest/tests`` (that package tests the engine, not this project's fixture
strategy). A silent regression here (e.g. the zero-std or insufficient-history guard)
would change the committed numbers without any red test.
"""

from __future__ import annotations

import numpy as np
import pytest

from core.backtest.guards import GuardedView
from demo_fixtures import DEMO_SEED, ZScoreMeanReversion, synthetic_prices


def test_synthetic_prices_is_deterministic() -> None:
    a = synthetic_prices(n=64, seed=DEMO_SEED)
    b = synthetic_prices(n=64, seed=DEMO_SEED)
    np.testing.assert_array_equal(a, b)


def test_synthetic_prices_different_seed_differs() -> None:
    a = synthetic_prices(n=64, seed=DEMO_SEED)
    b = synthetic_prices(n=64, seed=DEMO_SEED + 1)
    assert not np.array_equal(a, b)


def test_signal_flat_when_history_shorter_than_window() -> None:
    strategy = ZScoreMeanReversion(window=32)
    data = np.full(10, 100.0)  # shorter than the window
    view = GuardedView(data, t=5)
    assert strategy.signal(view) == 0.0


def test_signal_flat_when_recent_window_has_zero_variance() -> None:
    strategy = ZScoreMeanReversion(window=4)
    data = np.full(20, 100.0)  # constant series -> std == 0 in every window
    view = GuardedView(data, t=10)
    assert strategy.signal(view) == 0.0


def test_signal_shorts_when_price_is_rich_vs_recent_mean() -> None:
    strategy = ZScoreMeanReversion(window=4, z_scale=2.0)
    # Flat at 100 except a spike at t: recent mean/std computed on history <= t.
    data = np.array([100.0, 100.0, 100.0, 100.0, 110.0])
    view = GuardedView(data, t=4)
    signal = strategy.signal(view)
    assert signal < 0.0  # price above its recent mean -> short (mean reversion)


def test_signal_is_clipped_to_unit_bounds() -> None:
    strategy = ZScoreMeanReversion(window=4, z_scale=0.01)  # tiny z_scale -> huge |z / z_scale|
    data = np.array([100.0, 100.0, 100.0, 100.0, 999.0])
    view = GuardedView(data, t=4)
    assert strategy.signal(view) == pytest.approx(-1.0)


def test_signal_never_reads_beyond_t() -> None:
    """Point-in-time contract: history() must not leak values > t into the signal."""
    strategy = ZScoreMeanReversion(window=4)
    data = np.array([100.0, 100.0, 100.0, 100.0, 100.0, 1e9])  # future spike at index 5
    view = GuardedView(data, t=4)
    assert strategy.signal(view) == 0.0  # unaffected by the future spike at index 5
