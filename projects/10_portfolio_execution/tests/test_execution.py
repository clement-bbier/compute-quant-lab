"""Modèle d'exécution/coûts : linéaire (frais+slippage) + impact quadratique (test §6-b).

Convention P08 : coûts en **espace rendement** (appliqués à |Δpos|, pas ×prix). On prouve
l'identité turnover×frais (terme linéaire), la pénalité convexe d'impact, et la **parité** avec
l'accumulateur de référence du moteur P08 (oracle) quand l'impact est nul.
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
    """Terme linéaire : coût d'un trade = (frais+slippage)/1e4 · |Δpos|."""
    model = ExecutionModel(fees_bps=FEES_BPS, slippage_bps=SLIPPAGE_BPS, impact_kappa=0.0)
    assert model.cost(0.4) == pytest.approx(RATE * 0.4)
    assert model.cost(-0.4) == pytest.approx(RATE * 0.4)  # symétrique en signe


def test_total_linear_cost_equals_turnover_times_rate() -> None:
    """Sur un chemin, Σ coûts (linéaire) = turnover × taux (identité §6-b)."""
    positions = np.array([0.0, 1.0, 1.0, -0.5, 0.0], dtype=np.float64)
    gross = np.zeros_like(positions)
    model = ExecutionModel(fees_bps=FEES_BPS, slippage_bps=SLIPPAGE_BPS, impact_kappa=0.0)
    _, costs = model.apply(gross, positions)
    assert costs.sum() == pytest.approx(turnover(positions) * RATE)


def test_quadratic_impact_adds_to_cost() -> None:
    """Impact quadratique : coût = terme linéaire + κ·Δpos²."""
    kappa = 0.01
    model = ExecutionModel(fees_bps=FEES_BPS, slippage_bps=SLIPPAGE_BPS, impact_kappa=kappa)
    assert model.cost(0.5) == pytest.approx(RATE * 0.5 + kappa * 0.25)


def test_impact_is_convex_penalizes_large_rebalances() -> None:
    """Convexité : un gros trade coûte plus que deux moitiés (la capacité se paie)."""
    model = ExecutionModel(fees_bps=FEES_BPS, slippage_bps=SLIPPAGE_BPS, impact_kappa=0.01)
    assert model.cost(1.0) > 2.0 * model.cost(0.5)


def test_parity_with_p08_reference_loop_when_no_impact() -> None:
    """Sans impact, net = brut − coûts reproduit l'accumulateur de référence P08 (oracle)."""
    rng = np.random.default_rng(0)
    n = 64
    prices = np.clip(100.0 + np.cumsum(rng.standard_normal(n)), 1.0, None).astype(np.float64)
    positions = rng.integers(-1, 2, size=n).astype(np.float64)

    gross, _ = accumulate(positions, prices, 0.0, 0.0)  # rendements bruts (oracle, sans coût)
    net_oracle, _ = accumulate(positions, prices, FEES_BPS, SLIPPAGE_BPS)  # net oracle

    model = ExecutionModel(fees_bps=FEES_BPS, slippage_bps=SLIPPAGE_BPS, impact_kappa=0.0)
    net_mine, _ = model.apply(gross, positions)
    assert np.allclose(net_mine, net_oracle)


def test_apply_returns_net_equals_gross_minus_costs() -> None:
    """apply() renvoie (net, coûts) avec net = brut − coûts (littéral)."""
    positions = np.array([0.0, 1.0, 0.5, 0.0], dtype=np.float64)
    gross = np.array([0.0, 0.02, -0.01, 0.03], dtype=np.float64)
    model = ExecutionModel(fees_bps=FEES_BPS, slippage_bps=SLIPPAGE_BPS, impact_kappa=0.02)
    net, costs = model.apply(gross, positions)
    assert np.allclose(net, gross - costs)
