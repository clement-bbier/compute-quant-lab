"""Fixtures synthétiques + stratégie de démonstration (agnostique aux sources).

On prouve le moteur sans dépendre d'une donnée externe : une série mean-reverting
déterministe et une stratégie z-score strictement point-in-time (n'utilise que
`view.history()` ≤ t — elle ne déclenche jamais le garde-fou look-ahead).
"""

from __future__ import annotations

import numpy as np

from core.backtest.protocols import PointInTimeView

#: Graine de la fixture (reproductibilité de la démo).
DEMO_SEED: int = 42


def synthetic_prices(n: int = 512, seed: int = DEMO_SEED) -> np.ndarray:
    """Série de prix mean-reverting déterministe (processus OU discret autour de 100)."""
    rng = np.random.default_rng(seed)
    theta, mu, sigma = 0.05, 100.0, 1.0
    prices = np.empty(n, dtype=np.float64)
    prices[0] = mu
    for t in range(1, n):
        prices[t] = prices[t - 1] + theta * (mu - prices[t - 1]) + sigma * rng.standard_normal()
    return prices


class ZScoreMeanReversion:
    """Stratégie de mean-reversion : short quand le prix est cher vs sa moyenne mobile.

    Position cible = clip(-z / z_scale, -1, 1), où z est le z-score du dernier prix
    sur une fenêtre glissante. N'utilise QUE l'historique ≤ t (point-in-time).
    """

    def __init__(self, window: int = 32, z_scale: float = 2.0) -> None:
        self.window = window
        self.z_scale = z_scale

    def signal(self, view: PointInTimeView) -> float:
        history = view.history()  # données ≤ t uniquement
        if history.size < self.window:
            return 0.0  # historique insuffisant : on reste à plat
        recent = history[-self.window :]
        std = recent.std(ddof=1)
        if std == 0.0:
            return 0.0
        z = (view.latest() - recent.mean()) / std
        return float(np.clip(-z / self.z_scale, -1.0, 1.0))
