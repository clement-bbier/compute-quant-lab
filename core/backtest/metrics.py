"""Risk metrics for a backtest.

Pure functions over float64 arrays. The annualisation factor is always a
**keyword argument** (never a magic number buried in the code — see rule python-quality).
"""

from __future__ import annotations

import numpy as np

from core.backtest.protocols import FloatArray, Ledger


def cumulative_pnl(pnl: FloatArray) -> FloatArray:
    """Cumulative PnL: running sum of the period-by-period PnL."""
    return np.cumsum(pnl)


def sharpe_ratio(
    returns: FloatArray,
    periods_per_year: float,
    risk_free_rate: float = 0.0,
) -> float:
    """Annualised Sharpe ratio.

    Sharpe = mean(excess) / stdev(excess) · √(periods_per_year), where the excess
    subtracts the per-period risk-free rate (`risk_free_rate / periods_per_year`).
    Sample standard deviation (ddof=1). If volatility is zero, returns 0.0
    (Sharpe undefined -> explicit convention, no division by zero).
    """
    excess = returns - risk_free_rate / periods_per_year
    std = excess.std(ddof=1)
    if std == 0.0:
        return 0.0
    return float(excess.mean() / std * np.sqrt(periods_per_year))


def max_drawdown(equity_curve: FloatArray) -> float:
    """Worst peak-to-trough decline, as a *signed* fraction (≤ 0).

    E.g. equity [1, 2, 1.5, 3]: peak 2 -> trough 1.5 ⇒ -0.25. Increasing series ⇒ 0.0.
    """
    peak = np.maximum.accumulate(equity_curve)
    drawdown = equity_curve / peak - 1.0
    return float(drawdown.min())


def turnover(positions: FloatArray) -> float:
    """Gross turnover: total absolute position changes, starting from flat.

    E.g. positions [0, 1, 1, 0]: entry (+1) then exit (-1) ⇒ 2.0.
    """
    changes = np.diff(positions, prepend=0.0)
    return float(np.abs(changes).sum())


def hit_ratio(returns: FloatArray) -> float:
    """Fraction of periods with a strictly positive return (0.0 if the series is empty)."""
    if returns.size == 0:
        return 0.0
    return float((returns > 0.0).mean())


class DefaultMetrics:
    """Aggregates the mandatory metrics of a `Ledger` (implements MetricsCalculator).

    The annualisation factor and the risk-free rate are fixed at construction time.
    """

    def __init__(self, periods_per_year: float, risk_free_rate: float = 0.0) -> None:
        self.periods_per_year = periods_per_year
        self.risk_free_rate = risk_free_rate

    def compute(self, ledger: Ledger) -> dict[str, float]:
        """Return total PnL, Sharpe, max drawdown, turnover and hit ratio."""
        return {
            "pnl_total": float(ledger.pnl.sum()),
            "sharpe": sharpe_ratio(ledger.returns, self.periods_per_year, self.risk_free_rate),
            "max_drawdown": max_drawdown(ledger.equity_curve),
            "turnover": turnover(ledger.positions),
            "hit_ratio": hit_ratio(ledger.returns),
        }
