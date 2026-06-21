"""Fixtures partagées des tests P03 (volatilité + term structure).

Rend le code projet (sous ``src/``) importable comme modules de premier niveau
(``vol``, ``term_structure``, ``signal``, ``spot_series``), sur le modèle du
``conftest.py`` de P04. Les fixtures sont **déterministes** : pas d'aléa caché.
"""

from __future__ import annotations

import datetime as dt
import math
import sys
from pathlib import Path

import numpy as np
import pytest

# Rend les modules projet (sous src/) importables dans les tests.
_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

AS_OF = dt.datetime(2026, 6, 21, 0, 30, tzinfo=dt.timezone.utc)

# Amplitude de référence des returns alternés : vol par-période analytique connue.
KNOWN_RETURN_AMPLITUDE = 0.02


@pytest.fixture
def as_of() -> dt.datetime:
    return AS_OF


@pytest.fixture
def alternating_returns() -> np.ndarray:
    """Returns ±a alternés : écart-type de population par-période = a (connu)."""
    a = KNOWN_RETURN_AMPLITUDE
    return np.array([a, -a] * 60, dtype=float)


@pytest.fixture
def contango_curve() -> tuple[np.ndarray, np.ndarray]:
    """Courbe croissante (forward > spot) : pente attendue > 0."""
    maturities = np.array([0.0, 7.0, 30.0, 90.0, 180.0, 360.0])
    prices = 2.0 + 0.001 * maturities  # strictement croissante
    return maturities, prices


@pytest.fixture
def backwardation_curve() -> tuple[np.ndarray, np.ndarray]:
    """Courbe décroissante (forward < spot) : pente attendue < 0."""
    maturities = np.array([0.0, 7.0, 30.0, 90.0, 180.0, 360.0])
    prices = 2.0 - 0.001 * maturities  # strictement décroissante
    return maturities, prices


@pytest.fixture
def flat_curve() -> tuple[np.ndarray, np.ndarray]:
    """Courbe plate : pente ~ 0 (sous le seuil), forme attendue 'flat'."""
    maturities = np.array([0.0, 7.0, 30.0, 90.0, 180.0, 360.0])
    prices = np.full_like(maturities, 2.0)
    return maturities, prices


@pytest.fixture
def convex_curve() -> tuple[np.ndarray, np.ndarray]:
    """Courbe convexe (souriante) : courbure attendue > 0 (butterfly positif)."""
    maturities = np.array([0.0, 30.0, 60.0])
    prices = np.array([2.10, 2.00, 2.10])  # creux au milieu -> convexe
    return maturities, prices


def annualized(per_period_vol: float, periods_per_year: float = 365.0) -> float:
    """Annualise une vol par-période (helper de test, pas de magie cachée)."""
    return per_period_vol * math.sqrt(periods_per_year)
