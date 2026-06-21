"""Oracle Python pur de la phase 2 : accumulation du PnL période par période.

C'est la **spécification de référence** du noyau Rust `_loop`. La boucle Rust doit
reproduire *exactement* cette suite d'opérations float64 (même ordre de sommation)
pour garantir la parité bit-à-bit (`test_parity`).

Convention point-in-time (anti look-ahead) :
    rendement[t] = position[t-1] · (prix[t]/prix[t-1] − 1) − coût_de_rebalancement[t]
La position décidée en t-1 (sur données ≤ t-1) capte le mouvement de marché jusqu'à
t ; le rendement d'aujourd'hui ne dépend donc jamais de la position de demain.
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
    """Calcule la série de rendements et le nombre de trades.

    Parameters
    ----------
    positions, prices
        Tableaux float64 de même longueur (positions normalisées, prix de marché).
    fees_bps, slippage_bps
        Coûts en basis points appliqués à la variation absolue de position |Δpos|.

    Returns
    -------
    returns
        Rendement de la stratégie par période (sans dimension).
    n_trades
        Nombre de périodes où la position change.
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
