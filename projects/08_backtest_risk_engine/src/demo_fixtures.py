"""Synthetic fixtures + demonstration strategy (source-agnostic).

We prove out the engine without depending on external data: a deterministic
mean-reverting series and a strictly point-in-time z-score strategy (only uses
`view.history()` <= t — it never triggers the look-ahead guard).
"""

from __future__ import annotations

import numpy as np

from core.backtest.protocols import PointInTimeView

#: Fixture seed (demo reproducibility).
DEMO_SEED: int = 42


def synthetic_prices(n: int = 512, seed: int = DEMO_SEED) -> np.ndarray:
    """Deterministic mean-reverting price series (discrete OU process around 100)."""
    rng = np.random.default_rng(seed)
    theta, mu, sigma = 0.05, 100.0, 1.0
    prices = np.empty(n, dtype=np.float64)
    prices[0] = mu
    for t in range(1, n):
        prices[t] = prices[t - 1] + theta * (mu - prices[t - 1]) + sigma * rng.standard_normal()
    return prices


class ZScoreMeanReversion:
    """Mean-reversion strategy: short when the price is rich vs its moving average.

    Target position = clip(-z / z_scale, -1, 1), where z is the z-score of the latest
    price over a rolling window. Uses ONLY history <= t (point-in-time).
    """

    def __init__(self, window: int = 32, z_scale: float = 2.0) -> None:
        self.window = window
        self.z_scale = z_scale

    def signal(self, view: PointInTimeView) -> float:
        history = view.history()  # data <= t only
        if history.size < self.window:
            return 0.0  # insufficient history: stay flat
        recent = history[-self.window :]
        std = recent.std(ddof=1)
        if std == 0.0:
            return 0.0
        z = (view.latest() - recent.mean()) / std
        return float(np.clip(-z / self.z_scale, -1.0, 1.0))
