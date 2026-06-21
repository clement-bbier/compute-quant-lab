"""Moteur deux phases, bout-en-bout sur fixtures synthétiques.

Prouve notamment que le garde-fou look-ahead fait **échouer le run entier** quand
une stratégie triche (propriété non négociable, vérifiée à travers le moteur).
"""

from __future__ import annotations

import numpy as np
import pytest

from core.backtest.costs import LinearCostModel
from core.backtest.engine import BacktestEngine
from core.backtest.guards import LookAheadError
from core.backtest.protocols import BacktestResult, PointInTimeView


class BuyAndHold:
    """Toujours long 1 unité (n'utilise que l'instant courant ≤ t)."""

    def signal(self, view: PointInTimeView) -> float:
        return 1.0


class Cheating:
    """Adversaire : lit le prix de demain (t+1)."""

    def signal(self, view: PointInTimeView) -> float:
        return view.at(view.t + 1)


def _engine(fees_bps: float = 0.0, slippage_bps: float = 0.0) -> BacktestEngine:
    return BacktestEngine(
        cost_model=LinearCostModel(fees_bps=fees_bps, slippage_bps=slippage_bps),
        periods_per_year=252.0,
    )


def test_buy_and_hold_accounting_is_analytic():
    prices = np.array([100.0, 110.0, 121.0], dtype=np.float64)  # +10 % chaque pas
    result = _engine().run(prices, BuyAndHold())

    assert isinstance(result, BacktestResult)
    # returns = [0, 0.1, 0.1] -> PnL total 0.2 ; equity croissante -> DD 0 ; 1 trade.
    assert result.metrics["pnl_total"] == pytest.approx(0.2)
    assert result.metrics["max_drawdown"] == 0.0
    assert result.metrics["turnover"] == 1.0
    assert result.metrics["hit_ratio"] == pytest.approx(2.0 / 3.0)
    assert result.ledger.n_trades == 1


def test_engine_run_fails_when_strategy_cheats():
    prices = np.array([100.0, 110.0, 121.0], dtype=np.float64)
    with pytest.raises(LookAheadError):
        _engine().run(prices, Cheating())


def test_engine_is_deterministic(mean_reverting_prices):
    engine = _engine(fees_bps=10.0, slippage_bps=5.0)
    r1 = engine.run(mean_reverting_prices, BuyAndHold())
    r2 = engine.run(mean_reverting_prices, BuyAndHold())
    np.testing.assert_array_equal(r1.ledger.returns, r2.ledger.returns)
    assert r1.metrics == r2.metrics


def test_engine_records_params():
    prices = np.array([100.0, 110.0, 121.0], dtype=np.float64)
    result = _engine().run(prices, BuyAndHold(), params={"strategy": "buy_and_hold"})
    assert result.params["strategy"] == "buy_and_hold"
