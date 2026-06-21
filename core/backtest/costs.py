"""Modèles de coût injectables (frais + slippage).

Le coût est modélisé *explicitement* : c'est une exigence anti-illusion du labo
(un signal qui ne survit pas aux frais+slippage n'est pas un alpha).
"""

from __future__ import annotations

from core.backtest.protocols import Trade

#: 1 basis point = 1/10 000.
BPS: float = 10_000.0


class LinearCostModel:
    """Coût linéaire : (frais + slippage) en bps appliqués au notionnel absolu du trade."""

    def __init__(self, fees_bps: float, slippage_bps: float) -> None:
        self.fees_bps = fees_bps
        self.slippage_bps = slippage_bps

    def cost(self, trade: Trade) -> float:
        """Coût en euros = |delta_position · prix| · (frais + slippage) / 10 000."""
        notional = abs(trade.delta_position * trade.price)
        return notional * (self.fees_bps + self.slippage_bps) / BPS
