"""Anti look-ahead guard — the heart of the engine's discipline.

A strategy that *cheats* by reading data > t must make the run **fail** (raise
`LookAheadError`).
"""

from __future__ import annotations

import logging

import numpy as np
import pytest

from core.backtest.guards import GuardedView, LookAheadError
from core.backtest.protocols import PointInTimeView


def test_guard_raise_is_logged_at_error(caplog: pytest.LogCaptureFixture):
    """A look-ahead raise is a failed operation (observability rule) -> logged ERROR."""
    data = np.array([10.0, 11.0, 12.0, 13.0], dtype=np.float64)
    view = GuardedView(data, t=1)

    with caplog.at_level(logging.ERROR), pytest.raises(LookAheadError):
        view.at(2)

    assert any(record.levelno == logging.ERROR for record in caplog.records)
    assert "future access forbidden" in caplog.text


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
    # at(-1) in numpy = last element = the future when t < T-1. Explicitly forbidden.
    data = np.array([10.0, 11.0, 12.0, 13.0], dtype=np.float64)
    view = GuardedView(data, t=1)
    with pytest.raises(IndexError):
        view.at(-1)


def test_cheating_strategy_is_caught_by_the_guard():
    data = np.array([10.0, 11.0, 12.0, 13.0], dtype=np.float64)

    class CheatingStrategy:
        """Adversary: reads tomorrow's price (t+1) to generate its signal."""

        def signal(self, view: PointInTimeView) -> float:
            return view.at(view.t + 1)  # blatant look-ahead

    with pytest.raises(LookAheadError):
        CheatingStrategy().signal(GuardedView(data, t=1))


def test_honest_strategy_passes_through_the_guard():
    data = np.array([10.0, 11.0, 12.0, 13.0], dtype=np.float64)

    class HonestStrategy:
        """Uses only the history ≤ t: never trips the guard."""

        def signal(self, view: PointInTimeView) -> float:
            return float(view.history().mean())

    signal = HonestStrategy().signal(GuardedView(data, t=2))
    assert signal == np.array([10.0, 11.0, 12.0]).mean()
