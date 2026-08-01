"""``MeanReversionSignal``: spread mean reversion (hysteresis z-score, promoted from P02).

The tests check **decision parity** with the P02 hysteresis table (entry against the deviation,
exit through the dead band), the point-in-time behaviour (reset at ``t == 0``), and the
degenerate cases (short history, flat window).
"""

from __future__ import annotations

import numpy as np
import pytest

from core.backtest.guards import GuardedView
from core.signals.mean_reversion import MeanReversionSignal


def _signal() -> MeanReversionSignal:
    return MeanReversionSignal(z_entry=2.0, z_exit=0.5, lookback=20, simulated=True)


def test_invalid_band_is_rejected() -> None:
    """``z_exit >= z_entry`` (empty dead band) or ``lookback < 2`` raise at construction."""
    with pytest.raises(ValueError):
        MeanReversionSignal(z_entry=1.0, z_exit=1.0, lookback=20, simulated=True)
    with pytest.raises(ValueError):
        MeanReversionSignal(z_entry=2.0, z_exit=0.5, lookback=1, simulated=True)


def test_enters_against_deviation_when_flat() -> None:
    """When flat: ``z >= z_entry`` gives short (-1); ``z <= -z_entry`` gives long (+1), i.e. entry
    against the deviation."""
    sig = _signal()
    assert sig.decide(z=2.5, current_position=0.0) == -1.0
    assert sig.decide(z=-2.5, current_position=0.0) == 1.0
    assert sig.decide(z=1.0, current_position=0.0) == 0.0  # inside the band, stays flat


def test_holds_in_dead_band_and_exits_below_z_exit() -> None:
    """When in a position: holds while ``|z| > z_exit``; goes back to flat when ``|z| <= z_exit``."""
    sig = _signal()
    assert sig.decide(z=1.0, current_position=-1.0) == -1.0  # 0.5 < 1.0, holds
    assert sig.decide(z=0.3, current_position=-1.0) == 0.0  # 0.3 <= 0.5, exits
    assert sig.decide(z=-0.3, current_position=1.0) == 0.0


def test_fades_a_jump_above_recent_mean() -> None:
    """A jump above the recent mean (high z) makes the signal sell (position < 0)."""
    prices = np.concatenate([np.full(20, 100.0), np.array([100.0, 130.0])]).astype(np.float64)
    sig = MeanReversionSignal(z_entry=1.5, z_exit=0.5, lookback=20, simulated=True)
    # sequential pass (hysteresis state) up to the last step
    out = 0.0
    for t in range(prices.shape[0]):
        out = sig.signal(GuardedView(prices, t))
    assert out < 0.0


def test_resets_state_at_t_zero() -> None:
    """Two passes over the same series coincide: the state is reset at ``t == 0``."""
    prices = np.clip(100.0 + np.cumsum(np.random.default_rng(1).standard_normal(120)), 1.0, None)
    sig = _signal()
    first = [sig.signal(GuardedView(prices, t)) for t in range(prices.shape[0])]
    second = [sig.signal(GuardedView(prices, t)) for t in range(prices.shape[0])]
    assert first == second


def test_insufficient_history_or_flat_window_holds() -> None:
    """History shorter than ``lookback`` or a zero standard deviation keeps the position
    (0 at the start)."""
    short = np.array([100.0, 101.0], dtype=np.float64)
    assert _signal().signal(GuardedView(short, 1)) == 0.0
    flat = np.full(30, 100.0, dtype=np.float64)
    out = 0.0
    sig = _signal()
    for t in range(flat.shape[0]):
        out = sig.signal(GuardedView(flat, t))
    assert out == 0.0


def test_provenance_is_labelled() -> None:
    """The provenance carries the supplied name and simulated flag."""
    sig = MeanReversionSignal(z_entry=2.0, z_exit=0.5, lookback=20, name="p02", simulated=True)
    assert sig.name == "p02"
    assert sig.provenance.simulated is True
