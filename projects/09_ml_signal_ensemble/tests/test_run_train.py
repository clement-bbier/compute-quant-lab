"""Smoke test du pipeline headline : features → OOS → backtestable par P08.

Skippé proprement si le noyau Rust ``backtest_loop`` n'est pas compilé (CI en isolation),
de sorte que le gate reste vert sans build Rust ; exécuté pour de vrai quand il l'est.
"""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("backtest_loop")  # le moteur P08 importe le noyau Rust en dur

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
    # La plupart des lignes (hors warm-up / queue) reçoivent une prédiction OOS.
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
