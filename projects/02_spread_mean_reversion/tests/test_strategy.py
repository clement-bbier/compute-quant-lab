"""Tests de ``MeanReversionStrategy`` (bande à hystérésis sur z-score du spread).

Couvre : la règle de transition (pure), l'historique insuffisant, l'entrée/sortie par seuils,
l'anti look-ahead (garde-fou P08) et la réinitialisation d'état pour des runs reproductibles.
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
        MeanReversionStrategy(z_entry=1.0, z_exit=2.0, lookback=20)  # z_exit ≥ z_entry interdit


def test_decide_enters_against_the_deviation() -> None:
    strat = _strategy()
    assert strat.decide(z=3.0, current_position=0.0) == -1.0  # spread cher → short
    assert strat.decide(z=-3.0, current_position=0.0) == 1.0  # spread bas → long


def test_decide_holds_inside_band_and_exits_below_z_exit() -> None:
    strat = _strategy()
    assert strat.decide(z=1.5, current_position=-1.0) == -1.0  # |z|>z_exit → on tient
    assert strat.decide(z=0.3, current_position=-1.0) == 0.0  # |z|<z_exit → on sort à plat
    assert strat.decide(z=1.0, current_position=0.0) == 0.0  # zone morte, à plat → reste à plat


def test_signal_is_flat_with_insufficient_history() -> None:
    strat = _strategy(lookback=20)
    prices = np.linspace(1.0, 2.0, 50)
    assert strat.signal(GuardedView(prices, t=5)) == 0.0  # 6 points < lookback


def test_signal_enters_short_when_zscore_crosses_entry() -> None:
    lookback = 20
    strat = _strategy(lookback)
    window = np.concatenate(
        [np.full(lookback - 1, 1.0), [5.0]]
    )  # déviation haute en fin de fenêtre
    recent = window  # la fenêtre trailing inclut le point courant
    z = (window[-1] - recent.mean()) / recent.std(ddof=1)
    assert z > 2.0  # sanity : la déviation dépasse le seuil d'entrée
    assert strat.signal(GuardedView(window, t=lookback - 1)) == -1.0


def test_signal_enters_long_when_zscore_crosses_lower_entry() -> None:
    lookback = 20
    strat = _strategy(lookback)
    window = np.concatenate([np.full(lookback - 1, 1.0), [-3.0]])  # déviation basse
    assert strat.signal(GuardedView(window, t=lookback - 1)) == 1.0


def test_signal_resets_state_at_t0_for_reproducible_runs() -> None:
    lookback = 20
    strat = _strategy(lookback)
    window = np.concatenate([np.full(lookback - 1, 1.0), [5.0]])
    assert strat.signal(GuardedView(window, t=lookback - 1)) == -1.0  # prend une position
    assert strat._position == -1.0
    strat.signal(GuardedView(window, t=0))  # début d'un nouveau run → reset
    assert strat._position == 0.0


def test_cheating_strategy_is_caught_by_guard(mean_reverting_spread) -> None:
    """Une stratégie qui lit le futur via ``view.at(t+1)`` fait échouer le run (garde-fou P08)."""

    class Cheater:
        def signal(self, view: GuardedView) -> float:
            return view.at(view.t + 1)

    engine = BacktestEngine(
        cost_model=LinearCostModel(fees_bps=10.0, slippage_bps=5.0), periods_per_year=8760.0
    )
    with pytest.raises(LookAheadError):
        engine.run(mean_reverting_spread.to_numpy(), Cheater())
