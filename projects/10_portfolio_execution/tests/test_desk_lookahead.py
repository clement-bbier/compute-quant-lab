"""Anti look-ahead du desk composite (test §6-c).

La pondération à t ne doit dépendre que de signaux ≤ t. On le prouve de deux façons : muter
le futur ne change pas le passé (point-in-time), et un producteur tricheur (qui lit ``t+1``)
fait échouer le run via le garde-fou ``GuardedView`` de P08.
"""

from __future__ import annotations

import numpy as np
import pytest

from core.backtest import GuardedView, LookAheadError
from core.backtest.protocols import PointInTimeView

from desk import DeskStrategy
from portfolio import PortfolioConstructor
from provenance import SignalProvenance
from signals import MeanReversionMock, MomentumMock


def _positions_over(prices: np.ndarray) -> np.ndarray:
    """Génère la série de positions du desk (desk neuf, reset à t==0) via des GuardedView."""
    desk = DeskStrategy(
        producers=[MeanReversionMock(lookback=10), MomentumMock(lookback=15)],
        constructor=PortfolioConstructor(vol_floor=1e-4, gross_cap=1.0),
        vol_lookback=20,
    )
    return np.array([desk.signal(GuardedView(prices, t)) for t in range(prices.shape[0])])


def test_future_mutation_does_not_change_past_positions() -> None:
    """Muter les prix après l'instant k laisse inchangées toutes les positions ≤ k (point-in-time)."""
    rng = np.random.default_rng(3)
    n, k = 120, 60
    prices = np.clip(100.0 + np.cumsum(rng.standard_normal(n)), 1.0, None).astype(np.float64)
    mutated = prices.copy()
    mutated[k:] += 25.0  # on déforme franchement le futur

    pos_orig = _positions_over(prices)
    pos_mut = _positions_over(mutated)
    assert np.allclose(pos_orig[:k], pos_mut[:k])


class _CheatingMock:
    """Producteur tricheur : lit délibérément la valeur future ``t+1`` (interdit)."""

    name = "cheater"
    provenance = SignalProvenance(name="cheater", simulated=True)

    def signal(self, view: PointInTimeView) -> float:
        return view.at(view.t + 1)  # accès futur → doit lever LookAheadError


def test_cheating_producer_triggers_lookahead_error() -> None:
    """Un producteur qui lit le futur fait échouer le desk via le garde-fou P08."""
    prices = np.array([100.0, 101.0, 102.0, 103.0], dtype=np.float64)
    desk = DeskStrategy(
        producers=[_CheatingMock()],
        constructor=PortfolioConstructor(vol_floor=1e-4, gross_cap=1.0),
        vol_lookback=5,
    )
    with pytest.raises(LookAheadError):
        for t in range(prices.shape[0]):
            desk.signal(GuardedView(prices, t))
