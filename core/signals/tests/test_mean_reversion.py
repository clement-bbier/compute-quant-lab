"""``MeanReversionSignal`` : retour à la moyenne du spread (z-score à hystérésis, promu de P02).

On vérifie la **parité de décision** avec la table d'hystérésis P02 (entrée contre la déviation,
sortie par bande morte), le caractère point-in-time (reset à ``t == 0``), et les cas dégénérés
(historique court, fenêtre plate).
"""

from __future__ import annotations

import numpy as np
import pytest

from core.backtest.guards import GuardedView
from core.signals.mean_reversion import MeanReversionSignal


def _signal() -> MeanReversionSignal:
    return MeanReversionSignal(z_entry=2.0, z_exit=0.5, lookback=20, simulated=True)


def test_invalid_band_is_rejected() -> None:
    """``z_exit >= z_entry`` (bande morte vide) ou ``lookback < 2`` lèvent à la construction."""
    with pytest.raises(ValueError):
        MeanReversionSignal(z_entry=1.0, z_exit=1.0, lookback=20, simulated=True)
    with pytest.raises(ValueError):
        MeanReversionSignal(z_entry=2.0, z_exit=0.5, lookback=1, simulated=True)


def test_enters_against_deviation_when_flat() -> None:
    """À plat : ``z >= z_entry`` → short (-1) ; ``z <= -z_entry`` → long (+1) (entrée contre la déviation)."""
    sig = _signal()
    assert sig.decide(z=2.5, current_position=0.0) == -1.0
    assert sig.decide(z=-2.5, current_position=0.0) == 1.0
    assert sig.decide(z=1.0, current_position=0.0) == 0.0  # dans la bande → reste plat


def test_holds_in_dead_band_and_exits_below_z_exit() -> None:
    """En position : tient tant que ``|z| > z_exit`` ; repasse à plat quand ``|z| <= z_exit``."""
    sig = _signal()
    assert sig.decide(z=1.0, current_position=-1.0) == -1.0  # 0.5 < 1.0 → tient
    assert sig.decide(z=0.3, current_position=-1.0) == 0.0  # 0.3 <= 0.5 → sort
    assert sig.decide(z=-0.3, current_position=1.0) == 0.0


def test_fades_a_jump_above_recent_mean() -> None:
    """Saut au-dessus de la moyenne récente (z élevé) → le signal vend (position < 0)."""
    prices = np.concatenate([np.full(20, 100.0), np.array([100.0, 130.0])]).astype(np.float64)
    sig = MeanReversionSignal(z_entry=1.5, z_exit=0.5, lookback=20, simulated=True)
    # parcours séquentiel (état d'hystérésis) jusqu'au dernier instant
    out = 0.0
    for t in range(prices.shape[0]):
        out = sig.signal(GuardedView(prices, t))
    assert out < 0.0


def test_resets_state_at_t_zero() -> None:
    """Deux parcours sur la même série coïncident : l'état est réinitialisé à ``t == 0``."""
    prices = np.clip(100.0 + np.cumsum(np.random.default_rng(1).standard_normal(120)), 1.0, None)
    sig = _signal()
    first = [sig.signal(GuardedView(prices, t)) for t in range(prices.shape[0])]
    second = [sig.signal(GuardedView(prices, t)) for t in range(prices.shape[0])]
    assert first == second


def test_insufficient_history_or_flat_window_holds() -> None:
    """Historique plus court que ``lookback`` ou écart-type nul → on garde la position (0 au départ)."""
    short = np.array([100.0, 101.0], dtype=np.float64)
    assert _signal().signal(GuardedView(short, 1)) == 0.0
    flat = np.full(30, 100.0, dtype=np.float64)
    out = 0.0
    sig = _signal()
    for t in range(flat.shape[0]):
        out = sig.signal(GuardedView(flat, t))
    assert out == 0.0


def test_provenance_is_labelled() -> None:
    """La provenance porte le nom et le drapeau simulé fournis."""
    sig = MeanReversionSignal(z_entry=2.0, z_exit=0.5, lookback=20, name="p02", simulated=True)
    assert sig.name == "p02"
    assert sig.provenance.simulated is True
