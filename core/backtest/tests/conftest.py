"""Fixtures synthétiques *déterministes* du moteur de backtest.

Agnostique aux sources (cf. P08) : on prouve le moteur sur des séries connues,
à réponses analytiques, avant toute donnée externe. Graine fixée → reproductible.
"""

from __future__ import annotations

import numpy as np
import pytest

#: Graine unique de tout l'aléatoire des fixtures (reproductibilité).
SEED: int = 42


@pytest.fixture
def mean_reverting_prices() -> np.ndarray:
    """Série de prix mean-reverting déterministe (processus OU discret).

    Sert d'« historique long connu » pour la parité Rust↔Python et le déterminisme.
    """
    rng = np.random.default_rng(SEED)
    n = 512
    theta, mu, sigma = 0.05, 100.0, 1.0
    prices = np.empty(n, dtype=np.float64)
    prices[0] = mu
    for t in range(1, n):
        shock = sigma * rng.standard_normal()
        prices[t] = prices[t - 1] + theta * (mu - prices[t - 1]) + shock
    return prices


@pytest.fixture
def known_drawdown_equity() -> np.ndarray:
    """Courbe d'equity à drawdown analytique connu.

    Pic à 2.0 puis creux à 1.5 ⇒ max drawdown = (1.5 - 2.0) / 2.0 = -25 %.
    """
    return np.array([1.0, 2.0, 1.5, 3.0], dtype=np.float64)


@pytest.fixture
def flat_prices() -> np.ndarray:
    """Prix constants à 100 — isole la comptabilité des coûts du PnL de marché."""
    return np.full(8, 100.0, dtype=np.float64)
