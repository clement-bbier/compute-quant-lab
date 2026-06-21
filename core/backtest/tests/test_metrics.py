"""Métriques de risque sur séries *connues* (réponses analytiques)."""

from __future__ import annotations

import numpy as np

from core.backtest.metrics import (
    DefaultMetrics,
    cumulative_pnl,
    hit_ratio,
    max_drawdown,
    sharpe_ratio,
    turnover,
)
from core.backtest.protocols import Ledger


def test_sharpe_is_mean_over_std_annualised():
    # returns = [0.01, 0.03] : moyenne 0.02, écart-type (ddof=1) = sqrt(2e-4).
    # mean/std = 0.02 / (0.02/sqrt(2)) = sqrt(2) ; annualisé par sqrt(4) = 2.
    # => Sharpe = sqrt(2) * 2 = 2*sqrt(2).
    returns = np.array([0.01, 0.03], dtype=np.float64)
    s = sharpe_ratio(returns, periods_per_year=4.0)
    assert np.isclose(s, 2.0 * np.sqrt(2.0))


def test_sharpe_lowered_by_risk_free():
    returns = np.array([0.01, 0.03], dtype=np.float64)
    base = sharpe_ratio(returns, periods_per_year=4.0)
    with_rf = sharpe_ratio(returns, periods_per_year=4.0, risk_free_rate=0.04)
    assert with_rf < base


def test_sharpe_zero_volatility_returns_zero():
    # Volatilité nulle -> pas de division par zéro, Sharpe défini à 0.
    returns = np.array([0.01, 0.01, 0.01], dtype=np.float64)
    assert sharpe_ratio(returns, periods_per_year=252.0) == 0.0


def test_max_drawdown_analytic(known_drawdown_equity):
    # Pic 2.0 -> creux 1.5 => -25 %.
    assert max_drawdown(known_drawdown_equity) == -0.25


def test_max_drawdown_monotonic_increasing_is_zero():
    equity = np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float64)
    assert max_drawdown(equity) == 0.0


def test_turnover_counts_entry_and_exit():
    # Part à plat (0), entre (+1) puis sort (-1) => 2 unités brutes échangées.
    positions = np.array([0.0, 1.0, 1.0, 0.0], dtype=np.float64)
    assert turnover(positions) == 2.0


def test_hit_ratio_fraction_of_positive_periods():
    returns = np.array([0.01, -0.02, 0.03, 0.0], dtype=np.float64)
    assert hit_ratio(returns) == 0.5


def test_cumulative_pnl_is_running_sum():
    pnl = np.array([1.0, -1.0, 2.0], dtype=np.float64)
    np.testing.assert_array_equal(cumulative_pnl(pnl), np.array([1.0, 0.0, 2.0]))


def test_default_metrics_aggregates_known_ledger():
    ledger = Ledger(
        returns=np.array([0.01, 0.03], dtype=np.float64),
        pnl=np.array([1.0, 3.0], dtype=np.float64),
        equity_curve=np.array([101.0, 104.0], dtype=np.float64),
        positions=np.array([1.0, 1.0], dtype=np.float64),
        n_trades=1,
    )
    metrics = DefaultMetrics(periods_per_year=4.0).compute(ledger)
    assert set(metrics) == {"pnl_total", "sharpe", "max_drawdown", "turnover", "hit_ratio"}
    assert metrics["pnl_total"] == 4.0
    assert np.isclose(metrics["sharpe"], 2.0 * np.sqrt(2.0))
