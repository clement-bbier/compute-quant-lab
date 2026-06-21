"""Backtest bout-en-bout : ``MeanReversionStrategy`` sur le moteur P08, déterministe et causal.

Deux runs sur la même série doivent produire des métriques identiques (le reset d'état à t==0
empêche toute fuite entre runs). On vérifie aussi que la stratégie trade réellement la série
mean-reverting et que les cinq métriques de risque sont présentes.
"""

from __future__ import annotations

import numpy as np
from core.backtest import BacktestEngine, LinearCostModel

from strategy import MeanReversionStrategy


def _engine() -> BacktestEngine:
    return BacktestEngine(
        cost_model=LinearCostModel(fees_bps=10.0, slippage_bps=5.0), periods_per_year=8760.0
    )


def _strategy() -> MeanReversionStrategy:
    return MeanReversionStrategy(z_entry=1.5, z_exit=0.5, lookback=48)


def test_backtest_is_deterministic_across_runs(mean_reverting_spread) -> None:
    prices = mean_reverting_spread.to_numpy()
    strat = _strategy()
    engine = _engine()
    first = engine.run(prices, strat)
    second = engine.run(prices, strat)  # même instance : reset à t==0 → identité garantie
    np.testing.assert_array_equal(first.ledger.positions, second.ledger.positions)
    assert first.metrics == second.metrics


def test_backtest_exposes_risk_metrics_and_trades(mean_reverting_spread) -> None:
    result = _engine().run(mean_reverting_spread.to_numpy(), _strategy())
    assert set(result.metrics) == {"pnl_total", "sharpe", "max_drawdown", "turnover", "hit_ratio"}
    assert result.ledger.n_trades >= 1  # la stratégie entre/sort effectivement
