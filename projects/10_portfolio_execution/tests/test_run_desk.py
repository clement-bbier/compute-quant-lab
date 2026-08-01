"""Pure logic of the desk runner (excluding MLflow I/O): simulated series, net PnL, attribution, sensitivity.

We test the computational core of ``run_desk`` without touching MLflow: the price series is
labeled simulated, net PnL decomposes cleanly, and the sensitivity to impact cost κ
is monotone (more κ ⇒ less net PnL).
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
    """The desk price series is explicitly simulated and strictly positive (real/simulated rule)."""
    prices, provenance = build_synthetic_prices(n=300, seed=42)
    assert provenance.simulated is True
    assert prices.shape == (300,)
    assert np.all(prices > 0.0)


def test_default_producers_are_at_least_two_mocks() -> None:
    """The demo desk aggregates ≥ 2 mocked signals (PoC requirement §3)."""
    producers = DEFAULT_PRODUCERS()
    assert len(producers) >= 2
    assert all(p.provenance.simulated for p in producers)


def test_run_desk_backtest_net_is_gross_minus_costs() -> None:
    """The result exposes net = gross − costs and all mandatory risk metrics."""
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
    """The sum of per-signal contributions equals total gross PnL (exact attribution)."""
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
    """Cost sensitivity: a higher κ cannot increase net PnL (convex impact)."""
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
    assert net_pnls == sorted(net_pnls, reverse=True)  # decreasing in κ
