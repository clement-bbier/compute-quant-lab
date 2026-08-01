"""Execution/cost model: linear (fees+slippage) + quadratic impact (test §6-b).

P08 convention: costs in **return space** (applied to |Δpos|, not ×price). We prove
the turnover×fees identity (linear term), the convex impact penalty, and **parity** with
the P08 engine's reference accumulator (oracle) when impact is zero.
"""

from __future__ import annotations

import numpy as np
import pytest

from core.backtest.costs import BPS
from core.backtest.metrics import turnover
from core.backtest.reference_loop import accumulate

from execution import ExecutionModel

FEES_BPS, SLIPPAGE_BPS = 10.0, 5.0
RATE = (FEES_BPS + SLIPPAGE_BPS) / BPS


def test_linear_cost_equals_rate_times_abs_delta() -> None:
    """Linear term: cost of a trade = (fees+slippage)/1e4 · |Δpos|."""
    model = ExecutionModel(fees_bps=FEES_BPS, slippage_bps=SLIPPAGE_BPS, impact_kappa=0.0)
    assert model.cost(0.4) == pytest.approx(RATE * 0.4)
    assert model.cost(-0.4) == pytest.approx(RATE * 0.4)  # symmetric in sign


def test_total_linear_cost_equals_turnover_times_rate() -> None:
    """Over a path, Σ costs (linear) = turnover × rate (identity §6-b)."""
    positions = np.array([0.0, 1.0, 1.0, -0.5, 0.0], dtype=np.float64)
    gross = np.zeros_like(positions)
    model = ExecutionModel(fees_bps=FEES_BPS, slippage_bps=SLIPPAGE_BPS, impact_kappa=0.0)
    _, costs = model.apply(gross, positions)
    assert costs.sum() == pytest.approx(turnover(positions) * RATE)


def test_quadratic_impact_adds_to_cost() -> None:
    """Quadratic impact: cost = linear term + κ·Δpos²."""
    kappa = 0.01
    model = ExecutionModel(fees_bps=FEES_BPS, slippage_bps=SLIPPAGE_BPS, impact_kappa=kappa)
    assert model.cost(0.5) == pytest.approx(RATE * 0.5 + kappa * 0.25)


def test_impact_is_convex_penalizes_large_rebalances() -> None:
    """Convexity: a large trade costs more than two halves (capacity is priced in)."""
    model = ExecutionModel(fees_bps=FEES_BPS, slippage_bps=SLIPPAGE_BPS, impact_kappa=0.01)
    assert model.cost(1.0) > 2.0 * model.cost(0.5)


def test_parity_with_p08_reference_loop_when_no_impact() -> None:
    """Without impact, net = gross − costs reproduces the P08 reference accumulator (oracle)."""
    rng = np.random.default_rng(0)
    n = 64
    prices = np.clip(100.0 + np.cumsum(rng.standard_normal(n)), 1.0, None).astype(np.float64)
    positions = rng.integers(-1, 2, size=n).astype(np.float64)

    gross, _ = accumulate(positions, prices, 0.0, 0.0)  # gross returns (oracle, no cost)
    net_oracle, _ = accumulate(positions, prices, FEES_BPS, SLIPPAGE_BPS)  # net oracle

    model = ExecutionModel(fees_bps=FEES_BPS, slippage_bps=SLIPPAGE_BPS, impact_kappa=0.0)
    net_mine, _ = model.apply(gross, positions)
    assert np.allclose(net_mine, net_oracle)


def test_apply_returns_net_equals_gross_minus_costs() -> None:
    """apply() returns (net, costs) with net = gross − costs (literal)."""
    positions = np.array([0.0, 1.0, 0.5, 0.0], dtype=np.float64)
    gross = np.array([0.0, 0.02, -0.01, 0.03], dtype=np.float64)
    model = ExecutionModel(fees_bps=FEES_BPS, slippage_bps=SLIPPAGE_BPS, impact_kappa=0.02)
    net, costs = model.apply(gross, positions)
    assert np.allclose(net, gross - costs)
