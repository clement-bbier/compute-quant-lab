"""Pure-Python oracle for phase 2: period-by-period PnL accumulation.

This is the **reference specification** of the `_loop` Rust kernel. The Rust loop must
reproduce *exactly* this sequence of float64 operations (same summation order) to
guarantee bit-for-bit parity (`test_parity`).

Point-in-time convention (anti look-ahead):
    return[t] = position[t-1] · (price[t]/price[t-1] − 1) − rebalancing_cost[t]
The position decided at t-1 (from data ≤ t-1) captures the market move up to t, so
today's return never depends on tomorrow's position.
"""

from __future__ import annotations

import numpy as np

from core.backtest.costs import BPS
from core.backtest.protocols import FloatArray


def accumulate(
    positions: FloatArray,
    prices: FloatArray,
    fees_bps: float,
    slippage_bps: float,
) -> tuple[FloatArray, int]:
    """Compute the return series and the number of trades.

    Parameters
    ----------
    positions, prices
        float64 arrays of equal length (normalised positions, market prices).
    fees_bps, slippage_bps
        Costs in bps applied to the absolute position change |Δpos|.

    Returns
    -------
    returns
        Strategy return per period (dimensionless).
    n_trades
        Number of periods where the position changes.
    """
    n = positions.shape[0]
    cost_rate = (fees_bps + slippage_bps) / BPS
    returns = np.empty(n, dtype=np.float64)
    prev_pos = 0.0
    n_trades = 0
    for t in range(n):
        market_ret = 0.0 if t == 0 else prices[t] / prices[t - 1] - 1.0
        delta = positions[t] - prev_pos
        if delta != 0.0:
            n_trades += 1
        trade_cost = abs(delta) * cost_rate
        returns[t] = prev_pos * market_ret - trade_cost
        prev_pos = positions[t]
    return returns, n_trades
