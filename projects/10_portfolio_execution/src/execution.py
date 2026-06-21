"""Modèle d'exécution/coûts du desk : linéaire (frais+slippage) + impact quadratique.

Décision de design (PoC) : ``coût(Δpos) = (frais+slippage)/BPS · |Δpos| + κ · Δpos²``.
- Le terme **linéaire** épouse exactement la convention du moteur P08 (coûts en *espace
  rendement*, sur |Δpos|, pas ×prix) → parité bit-pour-bit avec ``reference_loop.accumulate``.
- Le terme **quadratique** (κ ≥ 0) modélise un *impact* convexe : sur-trader se paie, ce qui
  introduit une notion de **capacité** (un gros rebalancement coûte plus que deux petits).

C'est le « tueur de PnL » du desk (§10) : le PnL net se mesure après ce modèle, jamais le brut.
"""

from __future__ import annotations

import numpy as np

from core.backtest.costs import BPS
from core.backtest.protocols import FloatArray


class ExecutionModel:
    """Coûts d'exécution : frais+slippage linéaires + impact quadratique (espace rendement).

    Parameters
    ----------
    fees_bps, slippage_bps : float
        Frais et slippage en basis points, appliqués à |Δpos| (≥ 0).
    impact_kappa : float
        Coefficient d'impact quadratique κ ≥ 0 (0 = purement linéaire, parité P08).
    """

    def __init__(self, *, fees_bps: float, slippage_bps: float, impact_kappa: float) -> None:
        if min(fees_bps, slippage_bps, impact_kappa) < 0.0:
            raise ValueError("fees_bps, slippage_bps et impact_kappa doivent être ≥ 0.")
        self.fees_bps = fees_bps
        self.slippage_bps = slippage_bps
        self.impact_kappa = impact_kappa
        self._linear_rate = (fees_bps + slippage_bps) / BPS

    def _cost(self, delta: FloatArray | float) -> FloatArray | float:
        """Coût d'une (ou plusieurs) variation(s) de position — source unique de la formule."""
        return self._linear_rate * np.abs(delta) + self.impact_kappa * np.square(delta)

    def cost(self, delta_pos: float) -> float:
        """Coût d'un trade de taille ``delta_pos`` : ``rate·|Δ| + κ·Δ²`` (en rendement)."""
        return float(self._cost(delta_pos))

    def apply(
        self, gross_returns: FloatArray, positions: FloatArray
    ) -> tuple[FloatArray, FloatArray]:
        """Décompte du PnL net : net = brut − coûts de rebalancement, période par période.

        Le coût à t porte sur ``Δpos[t] = positions[t] − positions[t-1]`` (position initiale 0,
        convention du moteur P08). Renvoie ``(net_returns, cost_series)``, de même longueur.
        """
        deltas = np.diff(positions, prepend=0.0)
        cost_series = np.asarray(self._cost(deltas), dtype=np.float64)
        net_returns = gross_returns - cost_series
        return net_returns, cost_series
