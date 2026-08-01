"""Dependency injection: the desk runs on mocked signals, interchangeable scheme (§6-e).

The desk knows neither P02/P06/P09 nor the concrete weighting scheme: producers and
``WeightScheme`` are injected. We prove that we can (1) wire in ≥ 2 mocks and get a
non-trivial portfolio, (2) swap the allocation scheme without touching the desk's code (OCP).
"""

from __future__ import annotations

import numpy as np

from core.backtest import GuardedView
from core.backtest.protocols import FloatArray

from desk import DeskStrategy
from portfolio import InverseVolScheme, PortfolioConstructor
from signals import ConstantMock, MeanReversionMock, MomentumMock


class EqualWeightScheme:
    """Test-double: equal-weighted allocation, ignores vols. Proves that an arbitrary
    WeightScheme can be injected without modifying the desk or the PortfolioConstructor (OCP)."""

    def weights(self, vols: FloatArray, risk_budget: FloatArray | None = None) -> FloatArray:
        return np.full(vols.shape, 1.0 / vols.shape[0])


def _run(desk: DeskStrategy, prices: np.ndarray) -> np.ndarray:
    return np.array([desk.signal(GuardedView(prices, t)) for t in range(prices.shape[0])])


def test_desk_runs_with_two_injected_mocks(desk_prices: np.ndarray) -> None:
    """≥ 2 injected mocked producers → non-trivial portfolio (positions not all zero)."""
    desk = DeskStrategy(
        producers=[MeanReversionMock(lookback=10), MomentumMock(lookback=20)],
        constructor=PortfolioConstructor(InverseVolScheme(), vol_floor=1e-4, gross_cap=1.0),
        vol_lookback=20,
    )
    positions = _run(desk, desk_prices)
    assert np.any(positions != 0.0)


def test_swapping_weight_scheme_changes_allocation(desk_prices: np.ndarray) -> None:
    """Swapping WeightScheme (inverse-vol → equal-weight) changes the allocation, desk code unchanged."""
    producers = [ConstantMock(1.0), MeanReversionMock(lookback=10), MomentumMock(lookback=20)]
    desk_inv = DeskStrategy(
        producers=list(producers),
        constructor=PortfolioConstructor(InverseVolScheme(), vol_floor=1e-4, gross_cap=1.0),
        vol_lookback=20,
    )
    desk_eq = DeskStrategy(
        producers=list(producers),
        constructor=PortfolioConstructor(EqualWeightScheme(), vol_floor=1e-4, gross_cap=1.0),
        vol_lookback=20,
    )
    pos_inv = _run(desk_inv, desk_prices)
    pos_eq = _run(desk_eq, desk_prices)
    assert not np.allclose(pos_inv, pos_eq)
