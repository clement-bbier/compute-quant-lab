"""Anti look-ahead, per producer: the signal at ``t`` depends only on data ``<= t``.

Strong test (invariance to tampering with the future): each producer is evaluated in a
sequential pass up to ``T``, then the **prices after ``T`` are wrecked** and the pass is redone
up to ``T`` — the signal at ``T`` must be **identical**. That proves no future information enters.
The tests also check that a *cheating* producer (one that reads the future) raises through the
P08 ``GuardedView``.
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
    """Sequential pass ``0..upto`` (honours the hysteresis state), returning the signal at ``upto``."""
    out = 0.0
    for t in range(upto + 1):
        out = producer.signal(GuardedView(prices, t))
    return out


def _factories(n: int) -> list[Callable[[], SignalProducer]]:
    """One factory per producer (a fresh instance means a reset state), ML probabilities aligned
    on ``n``."""
    proba = np.random.default_rng(0).random(n).astype(np.float64)
    return [
        lambda: MeanReversionSignal(z_entry=1.5, z_exit=0.5, lookback=20, simulated=True),
        lambda: FuturesBasisSignal(tau_years=0.25, lookback=20),
        lambda: MLEnsembleSignal(proba, neutral_band=0.05, simulated=True),
    ]


def test_signal_is_invariant_to_tampering_the_future() -> None:
    """Tampering with the prices after ``T`` does not change the signal at ``T`` (no look-ahead)."""
    n, t_star = 120, 80
    prices = np.clip(
        100.0 + np.cumsum(np.random.default_rng(3).standard_normal(n)), 1.0, None
    ).astype(np.float64)
    tampered = prices.copy()
    tampered[t_star + 1 :] += 75.0  # large shock strictly in the future of T

    for make in _factories(n):
        original = _run_to(make(), prices, t_star)
        falsified = _run_to(make(), tampered, t_star)
        assert original == falsified


def test_cheating_producer_is_caught_by_the_guard() -> None:
    """A producer reading ``t + 1`` raises ``LookAheadError`` (the P08 guard cannot be bypassed)."""

    class _Cheater:
        name = "cheater"
        provenance = SignalProvenance(name="cheater", simulated=True)

        def signal(self, view: PointInTimeView) -> float:
            return view.at(view.t + 1)  # forbidden access to the future

    prices = np.arange(10, dtype=np.float64)
    with pytest.raises(LookAheadError):
        _Cheater().signal(GuardedView(prices, 5))
