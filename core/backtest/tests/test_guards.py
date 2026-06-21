"""Garde-fou anti look-ahead — le cœur de la discipline du moteur.

Le test mandaté (§6b) : une stratégie qui *triche* en lisant une donnée > t doit
faire **échouer** le run (lever `LookAheadError`). C'est le « rouge attendu ».
"""

from __future__ import annotations

import numpy as np
import pytest

from core.backtest.guards import GuardedView, LookAheadError
from core.backtest.protocols import PointInTimeView


def test_guard_exposes_only_data_up_to_t():
    data = np.array([10.0, 11.0, 12.0, 13.0], dtype=np.float64)
    view = GuardedView(data, t=2)
    assert view.latest() == 12.0
    assert view.at(0) == 10.0
    assert view.at(2) == 12.0
    np.testing.assert_array_equal(view.history(), np.array([10.0, 11.0, 12.0]))


def test_guard_raises_on_future_access():
    data = np.array([10.0, 11.0, 12.0, 13.0], dtype=np.float64)
    view = GuardedView(data, t=1)
    with pytest.raises(LookAheadError):
        view.at(2)


def test_guard_rejects_negative_index_to_block_wraparound_lookahead():
    # at(-1) en numpy = dernier élément = futur si t < T-1. On l'interdit explicitement.
    data = np.array([10.0, 11.0, 12.0, 13.0], dtype=np.float64)
    view = GuardedView(data, t=1)
    with pytest.raises(IndexError):
        view.at(-1)


def test_cheating_strategy_is_caught_by_the_guard():
    data = np.array([10.0, 11.0, 12.0, 13.0], dtype=np.float64)

    class CheatingStrategy:
        """Adversaire : lit le prix de demain (t+1) pour générer son signal."""

        def signal(self, view: PointInTimeView) -> float:
            return view.at(view.t + 1)  # look-ahead flagrant

    with pytest.raises(LookAheadError):
        CheatingStrategy().signal(GuardedView(data, t=1))


def test_honest_strategy_passes_through_the_guard():
    data = np.array([10.0, 11.0, 12.0, 13.0], dtype=np.float64)

    class HonestStrategy:
        """N'utilise que l'historique ≤ t : ne déclenche jamais le garde-fou."""

        def signal(self, view: PointInTimeView) -> float:
            return float(view.history().mean())

    signal = HonestStrategy().signal(GuardedView(data, t=2))
    assert signal == np.array([10.0, 11.0, 12.0]).mean()
