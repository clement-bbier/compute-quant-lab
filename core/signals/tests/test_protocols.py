"""Contrat de la couche signaux : ``SignalProducer`` (Protocol) + provenance obligatoire.

Les trois producteurs réels (mean-reversion, basis futures, ML) doivent être reconnus
comme ``SignalProducer`` (typage structurel) et porter une ``SignalProvenance`` dont le
drapeau ``simulated`` est **obligatoire** (rule ``forward-real-simulated``).
"""

from __future__ import annotations

import numpy as np
import pytest

from core.backtest.guards import GuardedView
from core.signals import (
    FuturesBasisSignal,
    MeanReversionSignal,
    MLEnsembleSignal,
    SignalProducer,
    SignalProvenance,
)


def _producers(n: int) -> list[SignalProducer]:
    """Les trois producteurs réels, avec une proba ML alignée sur ``n`` observations."""
    proba = np.full(n, 0.5, dtype=np.float64)
    return [
        MeanReversionSignal(z_entry=2.0, z_exit=0.5, lookback=20, simulated=True),
        FuturesBasisSignal(tau_years=0.25, lookback=20),
        MLEnsembleSignal(proba, simulated=True),
    ]


def test_all_producers_satisfy_protocol() -> None:
    """Chaque producteur réel est structurellement un ``SignalProducer`` (name, provenance, signal)."""
    for producer in _producers(8):
        assert isinstance(producer, SignalProducer)
        assert isinstance(producer.name, str) and producer.name


def test_provenance_flag_is_mandatory() -> None:
    """``SignalProvenance`` n'a pas de défaut pour ``simulated`` : l'oublier lève (frontière réel/simulé)."""
    with pytest.raises(TypeError):
        SignalProvenance(name="x")  # type: ignore[call-arg]


def test_every_producer_carries_a_simulated_flag() -> None:
    """Tout producteur expose ``provenance.simulated`` (booléen) — jamais d'étiquetage manquant."""
    for producer in _producers(8):
        assert isinstance(producer.provenance, SignalProvenance)
        assert isinstance(producer.provenance.simulated, bool)


def test_signal_output_is_bounded_unit_interval(prices: np.ndarray) -> None:
    """Toute sortie de producteur est une vue directionnelle dans [-1, 1] (contrat desk)."""
    for producer in _producers(prices.shape[0]):
        for t in range(prices.shape[0]):
            s = producer.signal(GuardedView(prices, t))
            assert -1.0 <= s <= 1.0
