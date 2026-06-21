"""Métriques de risque d'un backtest.

Fonctions pures sur des tableaux float64. Le facteur d'annualisation est toujours
un **argument nommé** (jamais un nombre magique enfoui — cf. rule python-quality).
"""

from __future__ import annotations

import numpy as np

from core.backtest.protocols import FloatArray, Ledger


def cumulative_pnl(pnl: FloatArray) -> FloatArray:
    """PnL cumulé : somme courante du PnL période par période."""
    return np.cumsum(pnl)


def sharpe_ratio(
    returns: FloatArray,
    periods_per_year: float,
    risk_free_rate: float = 0.0,
) -> float:
    """Ratio de Sharpe annualisé.

    Sharpe = moyenne(excès) / écart-type(excès) · √(periods_per_year), où l'excès
    retranche le taux sans risque par période (`risk_free_rate / periods_per_year`).
    Écart-type d'échantillon (ddof=1). Si la volatilité est nulle, renvoie 0.0
    (Sharpe non défini → convention explicite, pas de division par zéro).
    """
    excess = returns - risk_free_rate / periods_per_year
    std = excess.std(ddof=1)
    if std == 0.0:
        return 0.0
    return float(excess.mean() / std * np.sqrt(periods_per_year))


def max_drawdown(equity_curve: FloatArray) -> float:
    """Pire repli pic-à-creux, en fraction *signée* (≤ 0).

    Ex. equity [1, 2, 1.5, 3] : pic 2 → creux 1.5 ⇒ -0.25. Série croissante ⇒ 0.0.
    """
    peak = np.maximum.accumulate(equity_curve)
    drawdown = equity_curve / peak - 1.0
    return float(drawdown.min())


def turnover(positions: FloatArray) -> float:
    """Turnover brut : total des variations absolues de position, en partant à plat.

    Ex. positions [0, 1, 1, 0] : entrée (+1) puis sortie (-1) ⇒ 2.0.
    """
    changes = np.diff(positions, prepend=0.0)
    return float(np.abs(changes).sum())


def hit_ratio(returns: FloatArray) -> float:
    """Fraction de périodes à rendement strictement positif (0.0 si série vide)."""
    if returns.size == 0:
        return 0.0
    return float((returns > 0.0).mean())


class DefaultMetrics:
    """Agrège les métriques obligatoires d'un `Ledger` (implémente MetricsCalculator).

    Le facteur d'annualisation et le taux sans risque sont fixés à la construction.
    """

    def __init__(self, periods_per_year: float, risk_free_rate: float = 0.0) -> None:
        self.periods_per_year = periods_per_year
        self.risk_free_rate = risk_free_rate

    def compute(self, ledger: Ledger) -> dict[str, float]:
        """Renvoie PnL total, Sharpe, max drawdown, turnover et hit ratio."""
        return {
            "pnl_total": float(ledger.pnl.sum()),
            "sharpe": sharpe_ratio(
                ledger.returns, self.periods_per_year, self.risk_free_rate
            ),
            "max_drawdown": max_drawdown(ledger.equity_curve),
            "turnover": turnover(ledger.positions),
            "hit_ratio": hit_ratio(ledger.returns),
        }
