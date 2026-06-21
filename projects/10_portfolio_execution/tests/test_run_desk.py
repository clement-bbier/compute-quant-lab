"""Logique pure du runner desk (hors I/O MLflow) : série simulée, PnL net, attribution, sensibilité.

On teste le cœur calculatoire de ``run_desk`` sans toucher à MLflow : la série de prix est
étiquetée simulée, le PnL net se décompose proprement, et la sensibilité au coût d'impact κ
est monotone (plus de κ ⇒ moins de PnL net).
"""

from __future__ import annotations

import numpy as np
import pytest

from execution import ExecutionModel
from portfolio import PortfolioConstructor
from run_desk import (
    DEFAULT_PRODUCERS,
    build_synthetic_prices,
    cost_sensitivity,
    run_desk_backtest,
)
from signals import ConstantMock, MeanReversionMock, MomentumMock

PERIODS_PER_YEAR = 252.0
_REQUIRED_METRICS = {"pnl_total", "sharpe", "max_drawdown", "turnover", "hit_ratio"}


def test_synthetic_prices_are_simulated() -> None:
    """La série de prix desk est explicitement simulée et strictement positive (rule réel/simulé)."""
    prices, provenance = build_synthetic_prices(n=300, seed=42)
    assert provenance.simulated is True
    assert prices.shape == (300,)
    assert np.all(prices > 0.0)


def test_default_producers_are_at_least_two_mocks() -> None:
    """Le desk de démo agrège ≥ 2 signaux mockés (exigence PoC §3)."""
    producers = DEFAULT_PRODUCERS()
    assert len(producers) >= 2
    assert all(p.provenance.simulated for p in producers)


def test_run_desk_backtest_net_is_gross_minus_costs() -> None:
    """Le résultat expose net = brut − coûts et toutes les métriques de risque obligatoires."""
    prices, _ = build_synthetic_prices(n=400, seed=1)
    producers = [ConstantMock(1.0), MeanReversionMock(lookback=10), MomentumMock(lookback=20)]
    result = run_desk_backtest(
        prices,
        producers,
        PortfolioConstructor(vol_floor=1e-4, gross_cap=1.0),
        ExecutionModel(fees_bps=10.0, slippage_bps=5.0, impact_kappa=0.01),
        periods_per_year=PERIODS_PER_YEAR,
    )
    assert np.allclose(result.net_returns, result.gross_returns - result.costs)
    assert _REQUIRED_METRICS <= set(result.net_metrics)
    assert _REQUIRED_METRICS <= set(result.gross_metrics)


def test_attribution_sums_to_gross_pnl() -> None:
    """La somme des contributions par signal égale le PnL brut total (attribution exacte)."""
    prices, _ = build_synthetic_prices(n=400, seed=2)
    producers = [ConstantMock(1.0), MeanReversionMock(lookback=10), MomentumMock(lookback=20)]
    result = run_desk_backtest(
        prices,
        producers,
        PortfolioConstructor(vol_floor=1e-4, gross_cap=1.0),
        ExecutionModel(fees_bps=10.0, slippage_bps=5.0, impact_kappa=0.0),
        periods_per_year=PERIODS_PER_YEAR,
    )
    assert set(result.attribution) == {p.name for p in producers}
    assert sum(result.attribution.values()) == pytest.approx(result.gross_metrics["pnl_total"])


def test_cost_sensitivity_is_monotone_in_kappa() -> None:
    """Sensibilité au coût : un κ plus élevé ne peut pas augmenter le PnL net (impact convexe)."""
    prices, _ = build_synthetic_prices(n=400, seed=3)
    producers = [ConstantMock(1.0), MeanReversionMock(lookback=10), MomentumMock(lookback=20)]
    rows = cost_sensitivity(
        prices,
        producers,
        PortfolioConstructor(vol_floor=1e-4, gross_cap=1.0),
        kappas=[0.0, 0.01, 0.05, 0.1],
        fees_bps=10.0,
        slippage_bps=5.0,
        periods_per_year=PERIODS_PER_YEAR,
    )
    net_pnls = [row["net_pnl_total"] for row in rows]
    assert net_pnls == sorted(net_pnls, reverse=True)  # décroissant en κ
