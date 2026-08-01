"""Desk execution/cost model: linear (fees+slippage) + quadratic impact.

Design decision (PoC): ``cost(Δpos) = (fees+slippage)/BPS · |Δpos| + κ · Δpos²``.
- The **linear** term exactly matches the P08 engine's convention (costs in *return
  space*, on |Δpos|, not ×price) → bit-for-bit parity with ``reference_loop.accumulate``.
- The **quadratic** term (κ ≥ 0) models convex *impact*: over-trading costs more, which
  introduces a notion of **capacity** (one large rebalance costs more than two small ones).

This is the desk's "PnL killer" (§10): net PnL is measured after this model, never the gross.
"""

from __future__ import annotations

import numpy as np

from core.backtest.costs import BPS
from core.backtest.protocols import FloatArray


class ExecutionModel:
    """Execution costs: linear fees+slippage + quadratic impact (return space).

    Parameters
    ----------
    fees_bps, slippage_bps : float
        Fees and slippage in basis points, applied to |Δpos| (≥ 0).
    impact_kappa : float
        Quadratic impact coefficient κ ≥ 0 (0 = purely linear, P08 parity).
    """

    def __init__(self, *, fees_bps: float, slippage_bps: float, impact_kappa: float) -> None:
        if min(fees_bps, slippage_bps, impact_kappa) < 0.0:
            raise ValueError("fees_bps, slippage_bps and impact_kappa must be ≥ 0.")
        self.fees_bps = fees_bps
        self.slippage_bps = slippage_bps
        self.impact_kappa = impact_kappa
        self._linear_rate = (fees_bps + slippage_bps) / BPS

    def _cost(self, delta: FloatArray | float) -> FloatArray | float:
        """Cost of one (or several) position change(s) — single source of truth for the formula."""
        return self._linear_rate * np.abs(delta) + self.impact_kappa * np.square(delta)

    def cost(self, delta_pos: float) -> float:
        """Cost of a trade of size ``delta_pos``: ``rate·|Δ| + κ·Δ²`` (in return space)."""
        return float(self._cost(delta_pos))

    def apply(
        self, gross_returns: FloatArray, positions: FloatArray
    ) -> tuple[FloatArray, FloatArray]:
        """Net PnL accounting: net = gross − rebalancing costs, period by period.

        The cost at t applies to ``Δpos[t] = positions[t] − positions[t-1]`` (initial position 0,
        P08 engine convention). Returns ``(net_returns, cost_series)``, same length.
        """
        deltas = np.diff(positions, prepend=0.0)
        cost_series = np.asarray(self._cost(deltas), dtype=np.float64)
        net_returns = gross_returns - cost_series
        return net_returns, cost_series
