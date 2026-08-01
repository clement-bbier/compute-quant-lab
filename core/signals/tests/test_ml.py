"""``MLEnsembleSignal``: out-of-sample ML directional signal (wraps the P09 adapter).

The producer re-implements nothing: it **delegates** to ``PrecomputedSignalStrategy`` from
``core.models`` (P09). The tests therefore require **exact parity** with P09 (section 6b), the
switch to flat on ``NaN`` (warm-up / unobservable tail), and the labelled provenance.
"""

from __future__ import annotations

import numpy as np
import pytest

from core.backtest.guards import GuardedView
from core.models.strategy import PrecomputedSignalStrategy
from core.signals.ml import MLEnsembleSignal


def _proba(rng_seed: int, n: int) -> np.ndarray:
    """OOS probability vector in [0, 1] with a few ``NaN`` values (warm-up)."""
    rng = np.random.default_rng(rng_seed)
    proba = rng.random(n)
    proba[:5] = np.nan  # unpredicted warm-up
    return proba.astype(np.float64)


def test_parity_with_p09_precomputed_strategy() -> None:
    """The signal reproduces ``PrecomputedSignalStrategy`` from P09 **exactly**, for every ``t``
    and every neutral band."""
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
    """A ``NaN`` probability (no prediction available) gives a flat position (0)."""
    proba = np.array([np.nan, 0.9, 0.1], dtype=np.float64)
    prices = np.array([100.0, 101.0, 102.0], dtype=np.float64)
    producer = MLEnsembleSignal(proba, simulated=True)
    assert producer.signal(GuardedView(prices, 0)) == 0.0


def test_neutral_band_validation_propagates() -> None:
    """A neutral band outside ``[0, 0.5)`` raises (contract inherited from P09)."""
    proba = np.full(3, 0.5, dtype=np.float64)
    with pytest.raises(ValueError):
        MLEnsembleSignal(proba, neutral_band=0.6, simulated=True)


def test_provenance_is_labelled() -> None:
    """The provenance carries the name and the simulated flag (real/simulated boundary)."""
    proba = np.full(4, 0.5, dtype=np.float64)
    producer = MLEnsembleSignal(proba, name="p09", simulated=True)
    assert producer.name == "p09"
    assert producer.provenance.simulated is True
