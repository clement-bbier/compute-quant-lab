"""``MLEnsembleSignal`` : signal directionnel ML hors-échantillon (enveloppe l'adaptateur P09).

Le producteur ne ré-implémente rien : il **délègue** à ``PrecomputedSignalStrategy`` de
``core.models`` (P09). On exige donc la **parité exacte** avec P09 (§6b), le passage à plat sur
``NaN`` (warm-up / queue non observable), et la provenance étiquetée.
"""

from __future__ import annotations

import numpy as np
import pytest

from core.backtest.guards import GuardedView
from core.models.strategy import PrecomputedSignalStrategy
from core.signals.ml import MLEnsembleSignal


def _proba(rng_seed: int, n: int) -> np.ndarray:
    """Vecteur de probabilités OOS dans [0, 1] avec quelques ``NaN`` (warm-up)."""
    rng = np.random.default_rng(rng_seed)
    proba = rng.random(n)
    proba[:5] = np.nan  # warm-up non prédit
    return proba.astype(np.float64)


def test_parity_with_p09_precomputed_strategy() -> None:
    """Le signal reproduit **exactement** ``PrecomputedSignalStrategy`` de P09, ∀ t, ∀ bande neutre."""
    n = 64
    proba = _proba(7, n)
    prices = np.linspace(100.0, 120.0, n).astype(np.float64)
    for band in (0.0, 0.05, 0.2):
        reference = PrecomputedSignalStrategy(proba, neutral_band=band)
        producer = MLEnsembleSignal(proba, neutral_band=band, simulated=True)
        for t in range(n):
            view = GuardedView(prices, t)
            assert producer.signal(view) == reference.signal(view)


def test_nan_proba_is_flat() -> None:
    """Une proba ``NaN`` (pas de prédiction disponible) → position plate (0)."""
    proba = np.array([np.nan, 0.9, 0.1], dtype=np.float64)
    prices = np.array([100.0, 101.0, 102.0], dtype=np.float64)
    producer = MLEnsembleSignal(proba, simulated=True)
    assert producer.signal(GuardedView(prices, 0)) == 0.0


def test_neutral_band_validation_propagates() -> None:
    """Une bande neutre hors ``[0, 0.5)`` lève (contrat hérité de P09)."""
    proba = np.full(3, 0.5, dtype=np.float64)
    with pytest.raises(ValueError):
        MLEnsembleSignal(proba, neutral_band=0.6, simulated=True)


def test_provenance_is_labelled() -> None:
    """La provenance porte le nom et le drapeau simulé (frontière réel/simulé)."""
    proba = np.full(4, 0.5, dtype=np.float64)
    producer = MLEnsembleSignal(proba, name="p09", simulated=True)
    assert producer.name == "p09"
    assert producer.provenance.simulated is True
