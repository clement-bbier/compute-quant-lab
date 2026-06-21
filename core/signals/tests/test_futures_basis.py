"""``FuturesBasisSignal`` : carry/roll de la base future↔spot (sur le cost-of-carry de P06).

Mapping retenu (option A, *carry momentum*) : à ``t``, on price la base ``F − S`` via P06, puis
on rend le **z-score de la variation de base** sur la fenêtre ``<= t`` → on suit l'élargissement
de la base (saveur momentum, distincte du retour à la moyenne de P02).

Tests : point-in-time (historique court → plat) ; borné ; **réellement câblé sur P06** (un modèle
de portage en backwardation, ``k < 0``, inverse le signe) ; provenance simulée (forward non listé).
"""

from __future__ import annotations

import numpy as np

from core.backtest.guards import GuardedView
from core.pricing.derivatives.carry import CostOfCarryModel
from core.signals.futures_basis import FuturesBasisSignal


#: Série calme (plateau) suivie d'un saut net au tout dernier instant → momentum non ambigu.
def _calm_then_jump(jump: float, *, lookback: int) -> np.ndarray:
    base = np.full(lookback + 2, 100.0, dtype=np.float64)
    base[-1] = 100.0 + jump
    return base


def test_widening_basis_is_long_in_contango() -> None:
    """En contango (``r > y`` ⇒ base ∝ +spot), un saut haussier élargit la base → signal long (> 0)."""
    prices = _calm_then_jump(20.0, lookback=20)
    sig = FuturesBasisSignal(
        tau_years=0.25, lookback=20
    )  # CostOfCarryModel par défaut : r=0.04, y=0
    out = sig.signal(GuardedView(prices, prices.shape[0] - 1))
    assert out > 0.0


def test_narrowing_basis_is_short() -> None:
    """Un saut baissier resserre la base → signal short (< 0) — opposé du cas haussier."""
    prices = _calm_then_jump(-20.0, lookback=20)
    sig = FuturesBasisSignal(tau_years=0.25, lookback=20)
    out = sig.signal(GuardedView(prices, prices.shape[0] - 1))
    assert out < 0.0


def test_backwardation_model_flips_the_sign() -> None:
    """Preuve que P06 est vraiment câblé : un portage en backwardation (``y > r`` ⇒ ``k < 0``)
    inverse le signe du signal pour le **même** saut de prix."""
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
    """Moins de ``lookback + 1`` prix → pas assez de variations de base pour un z-score → plat (0)."""
    prices = np.full(10, 100.0, dtype=np.float64)
    assert FuturesBasisSignal(tau_years=0.25, lookback=20).signal(GuardedView(prices, 9)) == 0.0


def test_flat_window_is_flat() -> None:
    """Variation de base d'écart-type nul (prix constants) → pas de division par zéro, signal 0."""
    prices = np.full(40, 100.0, dtype=np.float64)
    assert FuturesBasisSignal(tau_years=0.25, lookback=20).signal(GuardedView(prices, 39)) == 0.0


def test_bounded_and_simulated(prices: np.ndarray) -> None:
    """Sortie bornée [-1, 1] sur toute la série ; provenance simulée (forward compute non listé)."""
    sig = FuturesBasisSignal(tau_years=0.25, lookback=20)
    assert sig.provenance.simulated is True
    for t in range(prices.shape[0]):
        assert -1.0 <= sig.signal(GuardedView(prices, t)) <= 1.0
