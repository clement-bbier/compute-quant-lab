"""Signal layer contract: ``SignalProducer`` (Protocol) + mandatory provenance.

The three real producers (mean-reversion, futures basis, ML) must be recognised as
``SignalProducer`` (structural typing) and carry a ``SignalProvenance`` whose ``simulated`` flag
is **mandatory** (rule ``forward-real-simulated``).
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
    """The three real producers, with ML probabilities aligned on ``n`` observations."""
    proba = np.full(n, 0.5, dtype=np.float64)
    return [
        MeanReversionSignal(z_entry=2.0, z_exit=0.5, lookback=20, simulated=True),
        FuturesBasisSignal(tau_years=0.25, lookback=20),
        MLEnsembleSignal(proba, simulated=True),
    ]


def test_all_producers_satisfy_protocol() -> None:
    """Every real producer is structurally a ``SignalProducer`` (name, provenance, signal)."""
    for producer in _producers(8):
        assert isinstance(producer, SignalProducer)
        assert isinstance(producer.name, str) and producer.name


def test_provenance_flag_is_mandatory() -> None:
    """``SignalProvenance`` has no default for ``simulated``: omitting it raises (real/simulated
    boundary)."""
    with pytest.raises(TypeError):
        SignalProvenance(name="x")  # type: ignore[call-arg]


def test_every_producer_carries_a_simulated_flag() -> None:
    """Every producer exposes ``provenance.simulated`` (a boolean) — labelling is never missing."""
    for producer in _producers(8):
        assert isinstance(producer.provenance, SignalProvenance)
        assert isinstance(producer.provenance.simulated, bool)


def test_signal_output_is_bounded_unit_interval(prices: np.ndarray) -> None:
    """Every producer output is a directional view in [-1, 1] (desk contract)."""
    for producer in _producers(prices.shape[0]):
        for t in range(prices.shape[0]):
            s = producer.signal(GuardedView(prices, t))
            assert -1.0 <= s <= 1.0
