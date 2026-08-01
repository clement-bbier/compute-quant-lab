"""Net PnL and per-signal attribution (test §6-d).

We wire the composite desk into the P08 engine (no-cost run = gross), then verify two
exact identities: the net position decomposes additively into per-signal contributions,
and ``Σ_i contribution_i == gross PnL``. Finally ``net = gross − costs`` via the execution model.
"""

from __future__ import annotations

import numpy as np

from core.backtest import BacktestEngine, LinearCostModel

from desk import DeskStrategy
from execution import ExecutionModel
from portfolio import PortfolioConstructor
from signals import ConstantMock, MeanReversionMock, MomentumMock

PERIODS_PER_YEAR = 252.0


def _desk() -> DeskStrategy:
    return DeskStrategy(
        producers=[ConstantMock(1.0), MeanReversionMock(lookback=10), MomentumMock(lookback=15)],
        constructor=PortfolioConstructor(vol_floor=1e-4, gross_cap=1.0),
        vol_lookback=20,
    )


def test_components_sum_to_net_position(desk_prices: np.ndarray) -> None:
    """The per-signal component positions sum exactly to the net position (additivity)."""
    desk = _desk()
    engine = BacktestEngine(cost_model=LinearCostModel(0.0, 0.0), periods_per_year=PERIODS_PER_YEAR)
    result = engine.run(desk_prices, desk)
    hist = desk.history()
    assert np.allclose(hist.components.sum(axis=1), result.ledger.positions)


def test_signal_contributions_sum_to_gross_pnl(desk_prices: np.ndarray) -> None:
    """Σ_i contribution_i[t] == gross return[t] (exact attribution, basis of 'contribution by signal')."""
    desk = _desk()
    engine = BacktestEngine(cost_model=LinearCostModel(0.0, 0.0), periods_per_year=PERIODS_PER_YEAR)
    result = engine.run(desk_prices, desk)
    hist = desk.history()
    gross = result.ledger.returns

    # contribution_i[t] = component_i[t-1] · market_return[t]
    contrib = hist.components[:-1] * hist.mkt_returns[1:].reshape(-1, 1)
    assert np.allclose(contrib.sum(axis=1), gross[1:])


def test_net_equals_gross_minus_costs(desk_prices: np.ndarray) -> None:
    """Net PnL = gross PnL − execution costs (the desk is judged on net, never on gross)."""
    desk = _desk()
    engine = BacktestEngine(cost_model=LinearCostModel(0.0, 0.0), periods_per_year=PERIODS_PER_YEAR)
    result = engine.run(desk_prices, desk)
    gross = result.ledger.returns
    positions = result.ledger.positions

    model = ExecutionModel(fees_bps=10.0, slippage_bps=5.0, impact_kappa=0.01)
    net, costs = model.apply(gross, positions)
    assert np.allclose(net, gross - costs)
    assert costs.sum() > 0.0  # the desk traded → strictly positive costs
