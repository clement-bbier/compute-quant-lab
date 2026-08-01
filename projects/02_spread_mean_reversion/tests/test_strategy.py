"""Tests for ``MeanReversionStrategy`` (hysteresis band on the spread's z-score).

Covers: the transition rule (pure), insufficient history, threshold entry/exit,
anti look-ahead (P08 guard), and state reset for reproducible runs.
"""

from __future__ import annotations

import numpy as np
import pytest
from core.backtest import BacktestEngine, GuardedView, LinearCostModel, LookAheadError

from strategy import MeanReversionStrategy


def _strategy(lookback: int = 20) -> MeanReversionStrategy:
    return MeanReversionStrategy(z_entry=2.0, z_exit=0.5, lookback=lookback)


def test_rejects_inconsistent_thresholds() -> None:
    with pytest.raises(ValueError):
        MeanReversionStrategy(z_entry=1.0, z_exit=2.0, lookback=20)  # z_exit >= z_entry forbidden


def test_decide_enters_against_the_deviation() -> None:
    strat = _strategy()
    assert strat.decide(z=3.0, current_position=0.0) == -1.0  # expensive spread -> short
    assert strat.decide(z=-3.0, current_position=0.0) == 1.0  # cheap spread -> long


def test_decide_holds_inside_band_and_exits_below_z_exit() -> None:
    strat = _strategy()
    assert strat.decide(z=1.5, current_position=-1.0) == -1.0  # |z|>z_exit -> hold
    assert strat.decide(z=0.3, current_position=-1.0) == 0.0  # |z|<z_exit -> flatten
    assert strat.decide(z=1.0, current_position=0.0) == 0.0  # dead zone, flat -> stays flat


def test_signal_is_flat_with_insufficient_history() -> None:
    strat = _strategy(lookback=20)
    prices = np.linspace(1.0, 2.0, 50)
    assert strat.signal(GuardedView(prices, t=5)) == 0.0  # 6 points < lookback


def test_signal_enters_short_when_zscore_crosses_entry() -> None:
    lookback = 20
    strat = _strategy(lookback)
    window = np.concatenate(
        [np.full(lookback - 1, 1.0), [5.0]]
    )  # high deviation at the end of the window
    recent = window  # the trailing window includes the current point
    z = (window[-1] - recent.mean()) / recent.std(ddof=1)
    assert z > 2.0  # sanity: the deviation exceeds the entry threshold
    assert strat.signal(GuardedView(window, t=lookback - 1)) == -1.0


def test_signal_enters_long_when_zscore_crosses_lower_entry() -> None:
    lookback = 20
    strat = _strategy(lookback)
    window = np.concatenate([np.full(lookback - 1, 1.0), [-3.0]])  # low deviation
    assert strat.signal(GuardedView(window, t=lookback - 1)) == 1.0


def test_signal_resets_state_at_t0_for_reproducible_runs() -> None:
    lookback = 20
    strat = _strategy(lookback)
    window = np.concatenate([np.full(lookback - 1, 1.0), [5.0]])
    assert strat.signal(GuardedView(window, t=lookback - 1)) == -1.0  # takes a position
    assert strat._position == -1.0
    strat.signal(GuardedView(window, t=0))  # start of a new run -> reset
    assert strat._position == 0.0


def test_cheating_strategy_is_caught_by_guard(mean_reverting_spread) -> None:
    """A strategy that reads the future via ``view.at(t+1)`` makes the run fail (P08 guard)."""

    class Cheater:
        def signal(self, view: GuardedView) -> float:
            return view.at(view.t + 1)

    engine = BacktestEngine(
        cost_model=LinearCostModel(fees_bps=10.0, slippage_bps=5.0), periods_per_year=8760.0
    )
    with pytest.raises(LookAheadError):
        engine.run(mean_reverting_spread.to_numpy(), Cheater())
