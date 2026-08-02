"""``FuturesBasisSignal``: carry/roll of the future/spot basis (on the P06 cost-of-carry).

Mapping (*carry momentum*): at ``t`` the basis ``F - S`` is priced through P06,
then the returned value is the **z-score of the basis change** over the window ``<= t``, so the
signal follows the widening of the basis (a momentum flavour, distinct from the P02 mean
reversion).

Tests: point-in-time (short history gives flat); bounded; **actually wired to P06** (a carry
model in backwardation, ``k < 0``, flips the sign); simulated provenance (unlisted forward).
"""

from __future__ import annotations

import numpy as np

from core.backtest.guards import GuardedView
from core.pricing.derivatives.carry import CostOfCarryModel
from core.signals.futures_basis import FuturesBasisSignal


#: Calm series (plateau) followed by a sharp jump at the very last step: unambiguous momentum.
def _calm_then_jump(jump: float, *, lookback: int) -> np.ndarray:
    base = np.full(lookback + 2, 100.0, dtype=np.float64)
    base[-1] = 100.0 + jump
    return base


def test_widening_basis_is_long_in_contango() -> None:
    """In contango (``r > y`` so basis is proportional to +spot), an upward jump widens the basis
    and the signal goes long (> 0)."""
    prices = _calm_then_jump(20.0, lookback=20)
    sig = FuturesBasisSignal(tau_years=0.25, lookback=20)  # default CostOfCarryModel: r=0.04, y=0
    out = sig.signal(GuardedView(prices, prices.shape[0] - 1))
    assert out > 0.0


def test_narrowing_basis_is_short() -> None:
    """A downward jump narrows the basis and the signal goes short (< 0), the opposite of the
    upward case."""
    prices = _calm_then_jump(-20.0, lookback=20)
    sig = FuturesBasisSignal(tau_years=0.25, lookback=20)
    out = sig.signal(GuardedView(prices, prices.shape[0] - 1))
    assert out < 0.0


def test_backwardation_model_flips_the_sign() -> None:
    """Proof that P06 is really wired in: a carry in backwardation (``y > r`` so ``k < 0``)
    flips the sign of the signal for the **same** price jump."""
    prices = _calm_then_jump(20.0, lookback=20)
    contango = FuturesBasisSignal(
        carry_model=CostOfCarryModel(rate=0.04, convenience_yield=0.0), tau_years=0.25, lookback=20
    )
    backwardation = FuturesBasisSignal(
        carry_model=CostOfCarryModel(rate=0.04, convenience_yield=0.20), tau_years=0.25, lookback=20
    )
    assert contango.signal(GuardedView(prices, prices.shape[0] - 1)) > 0.0
    assert backwardation.signal(GuardedView(prices, prices.shape[0] - 1)) < 0.0


def test_short_history_is_flat() -> None:
    """Fewer than ``lookback + 1`` prices: not enough basis changes for a z-score, so flat (0)."""
    prices = np.full(10, 100.0, dtype=np.float64)
    assert FuturesBasisSignal(tau_years=0.25, lookback=20).signal(GuardedView(prices, 9)) == 0.0


def test_flat_window_is_flat() -> None:
    """Zero standard deviation of the basis change (constant prices): no division by zero,
    signal 0."""
    prices = np.full(40, 100.0, dtype=np.float64)
    assert FuturesBasisSignal(tau_years=0.25, lookback=20).signal(GuardedView(prices, 39)) == 0.0


def test_bounded_and_simulated(prices: np.ndarray) -> None:
    """Output bounded to [-1, 1] over the whole series; simulated provenance (compute forward is
    not listed)."""
    sig = FuturesBasisSignal(tau_years=0.25, lookback=20)
    assert sig.provenance.simulated is True
    for t in range(prices.shape[0]):
        assert -1.0 <= sig.signal(GuardedView(prices, t)) <= 1.0
