"""Moteur de backtest reproductible + métriques de risque (fondation du labo).

Point-in-time, polyglotte (phase 2 Rust), garde-fou anti look-ahead intégré.
"""

from core.backtest.costs import LinearCostModel
from core.backtest.engine import BacktestEngine
from core.backtest.guards import GuardedView, LookAheadError
from core.backtest.metrics import (
    DefaultMetrics,
    cumulative_pnl,
    hit_ratio,
    max_drawdown,
    sharpe_ratio,
    turnover,
)
from core.backtest.protocols import (
    BacktestResult,
    CostModel,
    Ledger,
    MetricsCalculator,
    PointInTimeView,
    Strategy,
    Trade,
)

__all__ = [
    "BacktestEngine",
    "BacktestResult",
    "CostModel",
    "DefaultMetrics",
    "GuardedView",
    "Ledger",
    "LinearCostModel",
    "LookAheadError",
    "MetricsCalculator",
    "PointInTimeView",
    "Strategy",
    "Trade",
    "cumulative_pnl",
    "hit_ratio",
    "max_drawdown",
    "sharpe_ratio",
    "turnover",
]
