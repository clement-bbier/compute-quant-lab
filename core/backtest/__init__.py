"""Reproducible backtest engine + risk metrics (lab foundation).

Point-in-time, polyglot (Rust phase 2), with a built-in anti look-ahead guard.
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
