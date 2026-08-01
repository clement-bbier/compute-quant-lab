"""Wiring the **real** signals into the desk: P02 / P06 / P09 via ``core.signals`` (P12).

We replace the mocks with the real producers promoted into ``core.signals`` and prove the
desk runs on them **without changing its logic** (OCP): 3 real producers, all labeled simulated
(synthetic desk series at the PoC stage), net PnL = gross − costs, exact attribution, determinism.

A **lightweight** ML model is injected to keep the tests fast (the demo run itself uses
the seed-bagging ensemble by default).
"""

from __future__ import annotations

import numpy as np
import pytest

from core.models.xgboost_model import XGBoostDirectionModel
from core.signals import FuturesBasisSignal, MeanReversionSignal, MLEnsembleSignal, SignalProducer

from execution import ExecutionModel
from portfolio import PortfolioConstructor
from run_desk import REAL_PRODUCERS, build_synthetic_prices, run_desk_backtest

PERIODS_PER_YEAR = 252.0


def _fast_ml():
    """Builds a fast, deterministic ML model (few trees) for tests."""
    return lambda: XGBoostDirectionModel(random_state=0, n_estimators=30, max_depth=3)


def test_real_producers_are_three_real_signals() -> None:
    """``REAL_PRODUCERS`` instantiates exactly the 3 real producers (P02, P06, P09)."""
    prices, _ = build_synthetic_prices(n=260, seed=1)
    producers = REAL_PRODUCERS(prices, seed=1, ml_make_model=_fast_ml())
    assert len(producers) == 3
    kinds = {type(p) for p in producers}
    assert kinds == {MeanReversionSignal, FuturesBasisSignal, MLEnsembleSignal}
    for p in producers:
        assert isinstance(p, SignalProducer)


def test_real_producers_are_all_simulated() -> None:
    """At the PoC stage, the desk series is synthetic → every real signal stays labeled simulated (boundary)."""
    prices, _ = build_synthetic_prices(n=260, seed=2)
    producers = REAL_PRODUCERS(prices, seed=2, ml_make_model=_fast_ml())
    assert all(p.provenance.simulated for p in producers)


def test_desk_runs_on_real_signals_net_is_gross_minus_costs() -> None:
    """The desk runs on the **real** signals: net = gross − costs, metrics present."""
    prices, _ = build_synthetic_prices(n=320, seed=3)
    producers = REAL_PRODUCERS(prices, seed=3, ml_make_model=_fast_ml())
    result = run_desk_backtest(
        prices,
        producers,
        PortfolioConstructor(vol_floor=1e-4, gross_cap=1.0),
        ExecutionModel(fees_bps=10.0, slippage_bps=5.0, impact_kappa=0.01),
        periods_per_year=PERIODS_PER_YEAR,
    )
    assert np.allclose(result.net_returns, result.gross_returns - result.costs)
    assert {"pnl_total", "sharpe", "max_drawdown"} <= set(result.net_metrics)


def test_attribution_sums_to_gross_pnl_on_real_signals() -> None:
    """Exact attribution: the sum of the real signals' contributions = total gross PnL."""
    prices, _ = build_synthetic_prices(n=320, seed=4)
    producers = REAL_PRODUCERS(prices, seed=4, ml_make_model=_fast_ml())
    result = run_desk_backtest(
        prices,
        producers,
        PortfolioConstructor(vol_floor=1e-4, gross_cap=1.0),
        ExecutionModel(fees_bps=10.0, slippage_bps=5.0, impact_kappa=0.0),
        periods_per_year=PERIODS_PER_YEAR,
    )
    assert set(result.attribution) == {p.name for p in producers}
    assert sum(result.attribution.values()) == pytest.approx(result.gross_metrics["pnl_total"])


def test_real_producers_are_deterministic() -> None:
    """Two identical constructions + runs give the same result (fixed seed → reproducible)."""
    prices, _ = build_synthetic_prices(n=300, seed=5)
    constructor = PortfolioConstructor(vol_floor=1e-4, gross_cap=1.0)
    execution = ExecutionModel(fees_bps=10.0, slippage_bps=5.0, impact_kappa=0.02)
    a = run_desk_backtest(
        prices,
        REAL_PRODUCERS(prices, seed=5, ml_make_model=_fast_ml()),
        constructor,
        execution,
        periods_per_year=PERIODS_PER_YEAR,
    )
    b = run_desk_backtest(
        prices,
        REAL_PRODUCERS(prices, seed=5, ml_make_model=_fast_ml()),
        constructor,
        execution,
        periods_per_year=PERIODS_PER_YEAR,
    )
    assert np.allclose(a.net_returns, b.net_returns)
    assert a.attribution == b.attribution
