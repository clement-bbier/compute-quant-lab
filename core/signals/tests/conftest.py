"""Fixtures déterministes des tests de ``core.signals``.

On prouve chaque producteur de signal sur des séries connues (analytiques ou OU), à
graine fixée → reproductible (rule ``quant-no-lookahead``). Les producteurs sont
point-in-time : ils ne consomment que la ``GuardedView`` de P08 (données ≤ t).
"""

from __future__ import annotations

import numpy as np
import pytest

from core.backtest.protocols import FloatArray

#: Graine unique de tout l'aléatoire des fixtures (reproductibilité).
SEED: int = 42


def ou_series(n: int, *, theta: float = 0.08, sigma: float = 1.0, seed: int = SEED) -> FloatArray:
    """Série stationnaire d'Ornstein-Uhlenbeck (oscillation → matière au mean-reversion)."""
    rng = np.random.default_rng(seed)
    x = np.empty(n, dtype=np.float64)
    x[0] = 100.0
    for t in range(1, n):
        x[t] = x[t - 1] - theta * (x[t - 1] - 100.0) + sigma * rng.standard_normal()
    return x


@pytest.fixture
def prices() -> FloatArray:
    """Série de prix desk synthétique strictement positive (OU autour de 100)."""
    return np.clip(ou_series(256), 1.0, None).astype(np.float64)
