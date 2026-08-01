"""Smoke test of the headline pipeline: features → OOS → backtestable by P08.

Cleanly skipped if the Rust core ``backtest_loop`` isn't compiled (CI in isolation),
so the gate stays green without a Rust build; runs for real when it's available.
"""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("backtest_loop")  # the P08 engine hard-imports the Rust core

from core.backtest import BacktestEngine, LinearCostModel  # noqa: E402
from core.models import PrecomputedSignalStrategy  # noqa: E402
from run_train import build_features, out_of_sample_proba  # noqa: E402
from synthetic import generate  # noqa: E402

_EXPECTED_METRICS = {"pnl_total", "sharpe", "max_drawdown", "turnover", "hit_ratio"}


def test_features_and_labels_are_aligned_on_the_spread_index() -> None:
    dataset = generate(n_days=260)
    features, labels = build_features(dataset)
    assert features.index.equals(dataset.spread.index)
    assert len(labels) == len(dataset.spread)
    assert features.shape[1] > 0


def test_oos_proba_is_aligned_and_mostly_predicted() -> None:
    dataset = generate(n_days=260)
    features, labels = build_features(dataset)
    proba = out_of_sample_proba(features, labels)
    assert proba.shape == (len(dataset.spread),)
    # Most rows (outside warm-up / tail) receive an OOS prediction.
    assert np.isfinite(proba).mean() > 0.8


def test_signal_is_backtestable_by_p08() -> None:
    dataset = generate(n_days=260)
    features, labels = build_features(dataset)
    proba = out_of_sample_proba(features, labels)
    strategy = PrecomputedSignalStrategy(proba, neutral_band=0.05)
    engine = BacktestEngine(
        cost_model=LinearCostModel(fees_bps=10.0, slippage_bps=5.0),
        periods_per_year=365.0,
    )
    result = engine.run(dataset.spread.to_numpy(dtype=np.float64), strategy)
    assert _EXPECTED_METRICS <= set(result.metrics)
