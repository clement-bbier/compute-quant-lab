"""ML signal adapter -> ``Strategy`` of the P08 engine.

The model does not *see* the prices at runtime: the strategy merely reads the precomputed OOS
probability at ``view.t`` and maps it to a position. All leakage risk was neutralized upstream
(purged CV). What is tested here is the adapter, not the model.
"""

from __future__ import annotations

import numpy as np

# Submodules without a Rust dependency (see core.models.strategy): the suite stays
# executable without having compiled the `backtest_loop` kernel.
from core.backtest.guards import GuardedView
from core.backtest.protocols import Strategy
from core.models.strategy import PrecomputedSignalStrategy


def _view(n: int, t: int) -> GuardedView:
    """Real P08 point-in-time view over a dummy series (only ``.t`` is read)."""
    return GuardedView(np.zeros(n, dtype=np.float64), t)


def test_conforms_to_strategy_protocol() -> None:
    strat = PrecomputedSignalStrategy(np.full(10, 0.5), neutral_band=0.1)
    assert isinstance(strat, Strategy)


def test_returns_position_for_current_index() -> None:
    proba = np.array([0.9, 0.1, 0.5, 0.8, 0.2])
    strat = PrecomputedSignalStrategy(proba, neutral_band=0.1)
    positions = [strat.signal(_view(proba.size, t)) for t in range(proba.size)]
    assert positions == [1.0, -1.0, 0.0, 1.0, -1.0]


def test_neutral_band_keeps_uncertain_predictions_flat() -> None:
    proba = np.array([0.55, 0.45, 0.66, 0.34])
    strat = PrecomputedSignalStrategy(proba, neutral_band=0.10)
    positions = [strat.signal(_view(proba.size, t)) for t in range(proba.size)]
    # 0.55 and 0.45 are inside the band [0.40, 0.60] -> flat; 0.66/0.34 -> taken.
    assert positions == [0.0, 0.0, 1.0, -1.0]


def test_only_reads_current_index_never_future() -> None:
    """The position at ``t`` does not depend on the future of the probability series."""
    proba = np.array([0.8, 0.2, 0.9, 0.1, 0.7])
    strat = PrecomputedSignalStrategy(proba.copy(), neutral_band=0.05)
    t = 1
    before = strat.signal(_view(proba.size, t))
    tampered = proba.copy()
    tampered[t + 1 :] = 1.0  # force the entire future to "long"
    after = PrecomputedSignalStrategy(tampered, neutral_band=0.05).signal(_view(proba.size, t))
    assert before == after


def test_is_deterministic() -> None:
    proba = np.array([0.7, 0.3, 0.5, 0.6])
    a = [PrecomputedSignalStrategy(proba, neutral_band=0.0).signal(_view(4, t)) for t in range(4)]
    b = [PrecomputedSignalStrategy(proba, neutral_band=0.0).signal(_view(4, t)) for t in range(4)]
    assert a == b
