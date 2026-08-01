"""Injectable cost models (fees + slippage).

Cost is modelled *explicitly*: this is an anti-illusion requirement of the lab
(a signal that does not survive fees+slippage is not alpha).
"""

from __future__ import annotations

from core.backtest.protocols import Trade

#: 1 basis point = 1/10 000.
BPS: float = 10_000.0


class LinearCostModel:
    """Linear cost: (fees + slippage) in bps applied to the trade's absolute notional."""

    def __init__(self, fees_bps: float, slippage_bps: float) -> None:
        self.fees_bps = fees_bps
        self.slippage_bps = slippage_bps

    def cost(self, trade: Trade) -> float:
        """Cost in euros = |delta_position · price| · (fees + slippage) / 10 000."""
        notional = abs(trade.delta_position * trade.price)
        return notional * (self.fees_bps + self.slippage_bps) / BPS
