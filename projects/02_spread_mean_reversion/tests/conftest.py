"""Fixtures déterministes des tests P02 (cointégration + mean-reversion).

Séries synthétiques à propriétés *connues* : on prouve la détection de cointégration et
le signal de retour à la moyenne sur des cas analytiques **avant** toute donnée réelle.
Graine fixée partout → reproductible (rule ``quant-no-lookahead``).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Rend les modules du projet (sous src/) importables dans les tests, comme P04.
_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

#: Graine unique de tout l'aléatoire des fixtures (reproductibilité).
SEED: int = 42


def _utc_index(n: int) -> pd.DatetimeIndex:
    """Grille horaire UTC tz-aware de ``n`` points (exigence point-in-time du labo)."""
    return pd.date_range("2025-01-01", periods=n, freq="h", tz="UTC")


def _ornstein_uhlenbeck(
    n: int,
    *,
    theta: float,
    sigma: float,
    rng: np.random.Generator,
    x0: float = 0.0,
    mu: float = 0.0,
) -> np.ndarray:
    """Processus OU discret ``x[t] = x[t-1] + theta·(mu - x[t-1]) + sigma·N(0,1)`` (stationnaire)."""
    x = np.empty(n, dtype=np.float64)
    x[0] = x0
    for t in range(1, n):
        x[t] = x[t - 1] + theta * (mu - x[t - 1]) + sigma * rng.standard_normal()
    return x


@pytest.fixture
def cointegrated_pair() -> tuple[pd.Series, pd.Series, float]:
    """Couple cointégré *connu* : ``y = α + β·x + u``, x marche aléatoire I(1), u stationnaire (OU).

    Le résidu ``y - β·x`` est stationnaire → cointégration vraie. Renvoie ``(y, x, β)``.
    """
    rng = np.random.default_rng(SEED)
    n = 600
    x = 100.0 + np.cumsum(rng.standard_normal(n))  # marche aléatoire I(1)
    u = _ornstein_uhlenbeck(n, theta=0.10, sigma=1.0, rng=rng)  # résidu stationnaire
    alpha, beta = 5.0, 1.5
    y = alpha + beta * x + u
    idx = _utc_index(n)
    return pd.Series(y, index=idx, name="y"), pd.Series(x, index=idx, name="x"), beta


#: Graine d'une réalisation *franchement* non-cointégrée (Engle-Granger p≈0.96 sur 600 points).
#: Sous H0 « pas de cointégration », la p-value est ~uniforme : ~10 % des paires indépendantes
#: paraissent borderline (régression fallacieuse). On retient un cas clair pour un test non fragile.
_NON_COINTEGRATED_SEED: int = 5


@pytest.fixture
def independent_random_walks() -> tuple[pd.Series, pd.Series]:
    """Deux marches aléatoires *indépendantes* → non cointégrées (piège anti-spurious)."""
    rng = np.random.default_rng(_NON_COINTEGRATED_SEED)
    n = 600
    x = 100.0 + np.cumsum(rng.standard_normal(n))
    y = 50.0 + np.cumsum(rng.standard_normal(n))
    idx = _utc_index(n)
    return pd.Series(y, index=idx, name="y"), pd.Series(x, index=idx, name="x")


@pytest.fixture
def ou_spread_known_half_life() -> tuple[pd.Series, float]:
    """Spread OU à demi-vie *connue* : ``Δs = -λ·s + ε`` → demi-vie = ln(2)/λ."""
    rng = np.random.default_rng(SEED + 2)
    n = 3000
    lam = 0.10
    s = _ornstein_uhlenbeck(n, theta=lam, sigma=0.5, rng=rng)
    return pd.Series(s, index=_utc_index(n), name="spread"), float(np.log(2.0) / lam)


@pytest.fixture
def mean_reverting_spread() -> pd.Series:
    """Spread *positif* (OU autour de 2.0 $/GPU·h) pour un backtest déterministe réaliste."""
    rng = np.random.default_rng(SEED + 3)
    n = 512
    s = _ornstein_uhlenbeck(n, theta=0.05, sigma=0.05, rng=rng, x0=2.0, mu=2.0)
    return pd.Series(s, index=_utc_index(n), name="spread")
