"""Mocked signal producers (placeholders for P02/P06/P09): bounded, point-in-time, simulated.

At the PoC stage, these mocks stand in for the real signals. We only require that they produce
a directional view in [-1, 1] from data ≤ t, deterministic, labeled simulated.
"""

from __future__ import annotations

import numpy as np

from core.backtest import GuardedView
from signals import ConstantMock, MeanReversionMock, MomentumMock


def _signals_over(producer, prices: np.ndarray) -> np.ndarray:
    """Evaluates the producer at each t via a GuardedView (anti look-ahead) → signal series."""
    return np.array([producer.signal(GuardedView(prices, t)) for t in range(prices.shape[0])])


def test_constant_mock_returns_clipped_constant() -> None:
    """ConstantMock always returns its value, clipped to [-1, 1]."""
    prices = np.array([100.0, 101.0, 99.0, 102.0], dtype=np.float64)
    assert np.allclose(_signals_over(ConstantMock(value=0.5), prices), 0.5)
    assert np.allclose(_signals_over(ConstantMock(value=2.0), prices), 1.0)  # clipped


def test_all_mocks_bounded_in_unit_interval() -> None:
    """Every mocked signal stays within [-1, 1], regardless of price amplitude."""
    rng = np.random.default_rng(7)
    prices = 100.0 + np.cumsum(rng.standard_normal(200) * 3.0)
    for producer in (ConstantMock(1.0), MeanReversionMock(lookback=20), MomentumMock(lookback=20)):
        sig = _signals_over(producer, prices)
        assert np.all(sig >= -1.0) and np.all(sig <= 1.0)


def test_mean_reversion_fades_deviation() -> None:
    """On a jump above the recent mean, MeanReversionMock sells (signal < 0)."""
    prices = np.concatenate([np.full(20, 100.0), np.array([110.0])]).astype(np.float64)
    sig = MeanReversionMock(lookback=20).signal(GuardedView(prices, prices.shape[0] - 1))
    assert sig < 0.0


def test_momentum_rides_deviation() -> None:
    """On the same jump, MomentumMock follows the trend (signal > 0) — opposite of mean-reversion."""
    prices = np.concatenate([np.full(20, 100.0), np.array([110.0])]).astype(np.float64)
    sig = MomentumMock(lookback=20).signal(GuardedView(prices, prices.shape[0] - 1))
    assert sig > 0.0


def test_insufficient_history_is_flat() -> None:
    """History shorter than the lookback → neutral signal 0.0 (nothing to say, point-in-time)."""
    prices = np.array([100.0, 101.0], dtype=np.float64)
    assert MeanReversionMock(lookback=20).signal(GuardedView(prices, 1)) == 0.0
    assert MomentumMock(lookback=20).signal(GuardedView(prices, 1)) == 0.0


def test_mocks_are_simulated() -> None:
    """All mocked producers carry a simulated provenance (real/simulated boundary)."""
    for producer in (ConstantMock(1.0), MeanReversionMock(lookback=10), MomentumMock(lookback=10)):
        assert producer.provenance.simulated is True
        assert isinstance(producer.name, str) and producer.name


def test_zero_std_window_is_flat() -> None:
    """Flat window (zero standard deviation) → no division by zero, neutral signal 0.0."""
    prices = np.full(30, 100.0, dtype=np.float64)
    assert MeanReversionMock(lookback=20).signal(GuardedView(prices, 29)) == 0.0
    assert MomentumMock(lookback=20).signal(GuardedView(prices, 29)) == 0.0
