"""Fixtures déterministes des tests P09 (ensemble ML directionnel).

Deux familles de jeux synthétiques à propriétés *connues*, qui encodent la discipline
anti-overfitting dans la suite elle-même :

* ``predictable_dataset`` — la cible dépend d'une combinaison linéaire des features
  (+ bruit) : un modèle correct **doit** la retrouver (accuracy > hasard) ;
* ``noise_dataset`` — features et cible indépendantes : en validation OOS, un modèle
  honnête **ne doit pas** montrer de skill (accuracy ≈ 0.5). C'est le piège qui attrape
  l'illusion de backtest / la fuite de données.

Graine fixée partout → reproductible (rule ``quant-no-lookahead``).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

#: Graine unique de tout l'aléatoire des fixtures (reproductibilité).
SEED: int = 42


def _utc_index(n: int) -> pd.DatetimeIndex:
    """Grille horaire UTC tz-aware de ``n`` points (exigence point-in-time du labo)."""
    return pd.date_range("2025-01-01", periods=n, freq="h", tz="UTC")


@pytest.fixture
def predictable_dataset() -> tuple[np.ndarray, np.ndarray]:
    """``(X, y)`` où ``y`` suit un modèle logistique des features (signal apprenable).

    ``logit = X @ w`` avec ``w`` creux, puis ``y ~ Bernoulli(sigmoid(logit))`` : la
    relation est réelle mais bruitée, donc un bon classifieur dépasse nettement le hasard
    sans atteindre 100 %.
    """
    rng = np.random.default_rng(SEED)
    n, k = 800, 5
    x = rng.standard_normal((n, k))
    w = np.array([2.0, -1.5, 0.0, 0.0, 0.0])
    p = 1.0 / (1.0 + np.exp(-(x @ w)))
    y = (rng.random(n) < p).astype(np.float64)
    return x, y


@pytest.fixture
def noise_dataset() -> tuple[np.ndarray, np.ndarray]:
    """``(X, y)`` indépendants : aucun signal apprenable (sanity anti-overfitting)."""
    rng = np.random.default_rng(SEED + 1)
    n, k = 800, 5
    x = rng.standard_normal((n, k))
    y = (rng.random(n) < 0.5).astype(np.float64)
    return x, y


@pytest.fixture
def spread_series() -> pd.Series:
    """Spread synthétique (marche aléatoire bornée) pour tester labels & features PIT."""
    rng = np.random.default_rng(SEED + 2)
    n = 400
    values = 2.0 + np.cumsum(rng.standard_normal(n) * 0.05)
    return pd.Series(values, index=_utc_index(n), name="spread")
