"""Anti look-ahead for the composite desk (test §6-c).

The weighting at t must only depend on signals ≤ t. We prove this two ways: mutating
the future doesn't change the past (point-in-time), and a cheating producer (which reads
``t+1``) fails the run via P08's ``GuardedView`` guard.
"""

from __future__ import annotations

import numpy as np
import pytest

from core.backtest import GuardedView, LookAheadError
from core.backtest.protocols import PointInTimeView

from desk import DeskStrategy
from portfolio import PortfolioConstructor
from provenance import SignalProvenance
from signals import MeanReversionMock, MomentumMock


def _positions_over(prices: np.ndarray) -> np.ndarray:
    """Generates the desk's position series (fresh desk, reset at t==0) via GuardedViews."""
    desk = DeskStrategy(
        producers=[MeanReversionMock(lookback=10), MomentumMock(lookback=15)],
        constructor=PortfolioConstructor(vol_floor=1e-4, gross_cap=1.0),
        vol_lookback=20,
    )
    return np.array([desk.signal(GuardedView(prices, t)) for t in range(prices.shape[0])])


def test_future_mutation_does_not_change_past_positions() -> None:
    """Mutating prices after instant k leaves all positions ≤ k unchanged (point-in-time)."""
    rng = np.random.default_rng(3)
    n, k = 120, 60
    prices = np.clip(100.0 + np.cumsum(rng.standard_normal(n)), 1.0, None).astype(np.float64)
    mutated = prices.copy()
    mutated[k:] += 25.0  # deliberately distort the future

    pos_orig = _positions_over(prices)
    pos_mut = _positions_over(mutated)
    assert np.allclose(pos_orig[:k], pos_mut[:k])


class _CheatingMock:
    """Cheating producer: deliberately reads the future value ``t+1`` (forbidden)."""

    name = "cheater"
    provenance = SignalProvenance(name="cheater", simulated=True)

    def signal(self, view: PointInTimeView) -> float:
        return view.at(view.t + 1)  # future access → must raise LookAheadError


def test_cheating_producer_triggers_lookahead_error() -> None:
    """A producer that reads the future fails the desk via the P08 guard."""
    prices = np.array([100.0, 101.0, 102.0, 103.0], dtype=np.float64)
    desk = DeskStrategy(
        producers=[_CheatingMock()],
        constructor=PortfolioConstructor(vol_floor=1e-4, gross_cap=1.0),
        vol_lookback=5,
    )
    with pytest.raises(LookAheadError):
        for t in range(prices.shape[0]):
            desk.signal(GuardedView(prices, t))
