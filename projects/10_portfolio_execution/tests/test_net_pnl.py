"""PnL net et attribution par signal (test §6-d).

On branche le desk composite dans le moteur P08 (run sans coût = brut), puis on vérifie deux
identités exactes : la position nette se décompose additivement en contributions par signal,
et ``Σ_i contribution_i == PnL brut``. Enfin ``net = brut − coûts`` via le modèle d'exécution.
"""

from __future__ import annotations

import numpy as np

from core.backtest import BacktestEngine, LinearCostModel

from desk import DeskStrategy
from execution import ExecutionModel
from portfolio import PortfolioConstructor
from signals import ConstantMock, MeanReversionMock, MomentumMock

PERIODS_PER_YEAR = 252.0


def _desk() -> DeskStrategy:
    return DeskStrategy(
        producers=[ConstantMock(1.0), MeanReversionMock(lookback=10), MomentumMock(lookback=15)],
        constructor=PortfolioConstructor(vol_floor=1e-4, gross_cap=1.0),
        vol_lookback=20,
    )


def test_components_sum_to_net_position(desk_prices: np.ndarray) -> None:
    """Les positions-composantes par signal somment exactement à la position nette (additivité)."""
    desk = _desk()
    engine = BacktestEngine(cost_model=LinearCostModel(0.0, 0.0), periods_per_year=PERIODS_PER_YEAR)
    result = engine.run(desk_prices, desk)
    hist = desk.history()
    assert np.allclose(hist.components.sum(axis=1), result.ledger.positions)


def test_signal_contributions_sum_to_gross_pnl(desk_prices: np.ndarray) -> None:
    """Σ_i contribution_i[t] == rendement brut[t] (attribution exacte, base de 'contribution par signal')."""
    desk = _desk()
    engine = BacktestEngine(cost_model=LinearCostModel(0.0, 0.0), periods_per_year=PERIODS_PER_YEAR)
    result = engine.run(desk_prices, desk)
    hist = desk.history()
    gross = result.ledger.returns

    # contribution_i[t] = composante_i[t-1] · rendement_marché[t]
    contrib = hist.components[:-1] * hist.mkt_returns[1:].reshape(-1, 1)
    assert np.allclose(contrib.sum(axis=1), gross[1:])


def test_net_equals_gross_minus_costs(desk_prices: np.ndarray) -> None:
    """PnL net = PnL brut − coûts d'exécution (le desk se juge au net, jamais au brut)."""
    desk = _desk()
    engine = BacktestEngine(cost_model=LinearCostModel(0.0, 0.0), periods_per_year=PERIODS_PER_YEAR)
    result = engine.run(desk_prices, desk)
    gross = result.ledger.returns
    positions = result.ledger.positions

    model = ExecutionModel(fees_bps=10.0, slippage_bps=5.0, impact_kappa=0.01)
    net, costs = model.apply(gross, positions)
    assert np.allclose(net, gross - costs)
    assert costs.sum() > 0.0  # le desk a tradé → coûts strictement positifs
