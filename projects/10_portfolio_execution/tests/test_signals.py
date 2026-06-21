"""Producteurs de signaux mockés (placeholders P02/P06/P09) : bornés, point-in-time, simulés.

Au PoC, ces mocks tiennent la place des vrais signaux. On exige seulement qu'ils produisent
une vue directionnelle dans [-1, 1] à partir de données ≤ t, déterministe, étiquetée simulée.
"""

from __future__ import annotations

import numpy as np

from core.backtest import GuardedView
from signals import ConstantMock, MeanReversionMock, MomentumMock


def _signals_over(producer, prices: np.ndarray) -> np.ndarray:
    """Évalue le producteur à chaque t via une GuardedView (anti look-ahead) → série de signaux."""
    return np.array([producer.signal(GuardedView(prices, t)) for t in range(prices.shape[0])])


def test_constant_mock_returns_clipped_constant() -> None:
    """ConstantMock rend toujours sa valeur, écrêtée à [-1, 1]."""
    prices = np.array([100.0, 101.0, 99.0, 102.0], dtype=np.float64)
    assert np.allclose(_signals_over(ConstantMock(value=0.5), prices), 0.5)
    assert np.allclose(_signals_over(ConstantMock(value=2.0), prices), 1.0)  # écrêté


def test_all_mocks_bounded_in_unit_interval() -> None:
    """Tout signal mocké reste dans [-1, 1], quelle que soit l'amplitude des prix."""
    rng = np.random.default_rng(7)
    prices = 100.0 + np.cumsum(rng.standard_normal(200) * 3.0)
    for producer in (ConstantMock(1.0), MeanReversionMock(lookback=20), MomentumMock(lookback=20)):
        sig = _signals_over(producer, prices)
        assert np.all(sig >= -1.0) and np.all(sig <= 1.0)


def test_mean_reversion_fades_deviation() -> None:
    """Sur un saut au-dessus de la moyenne récente, MeanReversionMock vend (signal < 0)."""
    prices = np.concatenate([np.full(20, 100.0), np.array([110.0])]).astype(np.float64)
    sig = MeanReversionMock(lookback=20).signal(GuardedView(prices, prices.shape[0] - 1))
    assert sig < 0.0


def test_momentum_rides_deviation() -> None:
    """Sur le même saut, MomentumMock suit la tendance (signal > 0) — opposé du mean-reversion."""
    prices = np.concatenate([np.full(20, 100.0), np.array([110.0])]).astype(np.float64)
    sig = MomentumMock(lookback=20).signal(GuardedView(prices, prices.shape[0] - 1))
    assert sig > 0.0


def test_insufficient_history_is_flat() -> None:
    """Historique plus court que le lookback → signal neutre 0.0 (rien à dire, point-in-time)."""
    prices = np.array([100.0, 101.0], dtype=np.float64)
    assert MeanReversionMock(lookback=20).signal(GuardedView(prices, 1)) == 0.0
    assert MomentumMock(lookback=20).signal(GuardedView(prices, 1)) == 0.0


def test_mocks_are_simulated() -> None:
    """Tous les producteurs mockés portent une provenance simulée (frontière réel/simulé)."""
    for producer in (ConstantMock(1.0), MeanReversionMock(lookback=10), MomentumMock(lookback=10)):
        assert producer.provenance.simulated is True
        assert isinstance(producer.name, str) and producer.name


def test_zero_std_window_is_flat() -> None:
    """Fenêtre plate (écart-type nul) → pas de division par zéro, signal neutre 0.0."""
    prices = np.full(30, 100.0, dtype=np.float64)
    assert MeanReversionMock(lookback=20).signal(GuardedView(prices, 29)) == 0.0
    assert MomentumMock(lookback=20).signal(GuardedView(prices, 29)) == 0.0
