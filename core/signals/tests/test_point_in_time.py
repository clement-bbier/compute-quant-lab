"""Anti look-ahead, par producteur : le signal à ``t`` ne dépend que des données ``<= t``.

Test fort (invariance à la falsification du futur, §6a) : on évalue chaque producteur en parcours
séquentiel jusqu'à ``T``, puis on **saccage les prix après ``T``** et on ré-évalue jusqu'à ``T`` —
le signal à ``T`` doit être **identique**. C'est la preuve qu'aucune information future n'entre.
On vérifie aussi qu'un producteur *tricheur* (qui lit le futur) lève via la ``GuardedView`` de P08.
"""

from __future__ import annotations

from typing import Callable

import numpy as np
import pytest

from core.backtest.guards import GuardedView, LookAheadError
from core.backtest.protocols import PointInTimeView
from core.signals import (
    FuturesBasisSignal,
    MeanReversionSignal,
    MLEnsembleSignal,
    SignalProducer,
    SignalProvenance,
)


def _run_to(producer: SignalProducer, prices: np.ndarray, upto: int) -> float:
    """Parcours séquentiel ``0..upto`` (respecte l'état d'hystérésis) → signal à ``upto``."""
    out = 0.0
    for t in range(upto + 1):
        out = producer.signal(GuardedView(prices, t))
    return out


def _factories(n: int) -> list[Callable[[], SignalProducer]]:
    """Une fabrique par producteur (instance neuve = état réinitialisé), proba ML alignée sur ``n``."""
    proba = np.random.default_rng(0).random(n).astype(np.float64)
    return [
        lambda: MeanReversionSignal(z_entry=1.5, z_exit=0.5, lookback=20, simulated=True),
        lambda: FuturesBasisSignal(tau_years=0.25, lookback=20),
        lambda: MLEnsembleSignal(proba, neutral_band=0.05, simulated=True),
    ]


def test_signal_is_invariant_to_tampering_the_future() -> None:
    """Falsifier les prix après ``T`` ne change pas le signal à ``T`` (aucun look-ahead)."""
    n, t_star = 120, 80
    prices = np.clip(
        100.0 + np.cumsum(np.random.default_rng(3).standard_normal(n)), 1.0, None
    ).astype(np.float64)
    tampered = prices.copy()
    tampered[t_star + 1 :] += 75.0  # gros choc strictement dans le futur de T

    for make in _factories(n):
        original = _run_to(make(), prices, t_star)
        falsified = _run_to(make(), tampered, t_star)
        assert original == falsified


def test_cheating_producer_is_caught_by_the_guard() -> None:
    """Un producteur qui lit ``t + 1`` lève ``LookAheadError`` (garde-fou P08 non contournable)."""

    class _Cheater:
        name = "cheater"
        provenance = SignalProvenance(name="cheater", simulated=True)

        def signal(self, view: PointInTimeView) -> float:
            return view.at(view.t + 1)  # accès futur interdit

    prices = np.arange(10, dtype=np.float64)
    with pytest.raises(LookAheadError):
        _Cheater().signal(GuardedView(prices, 5))
