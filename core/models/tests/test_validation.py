"""Temporal validation: purged k-fold + embargo, leak-free OOS, deflated Sharpe.

Heart of the anti-overfitting defense (Lopez de Prado). The tests prove the absence of
train/test overlap *at the level of the label horizon* (not only of the indices), and that
the Deflated Sharpe does penalize multiple-testing.
"""

from __future__ import annotations

import numpy as np
import pytest

from core.models.validation import (
    PurgedKFold,
    deflated_sharpe_ratio,
    expected_max_sharpe,
    oos_predict,
    sharpe_confidence_interval,
    sharpe_standard_error,
    sharpe_t_stat,
)
from core.models.xgboost_model import XGBoostDirectionModel

N_SAMPLES = 200
HORIZON = 5
EMBARGO = 3


def _folds(n_splits: int = 5, *, horizon: int = HORIZON, embargo: int = EMBARGO):
    splitter = PurgedKFold(n_splits=n_splits, horizon=horizon, embargo=embargo)
    return list(splitter.split(N_SAMPLES))


def test_train_and_test_are_disjoint() -> None:
    for train, test in _folds():
        assert set(train.tolist()).isdisjoint(test.tolist())


def test_test_blocks_are_contiguous_and_ordered() -> None:
    """No shuffle: each test block is a contiguous, increasing segment."""
    test_blocks = [test for _, test in _folds()]
    for test in test_blocks:
        assert np.array_equal(test, np.arange(test[0], test[-1] + 1))
    starts = [int(test[0]) for test in test_blocks]
    assert starts == sorted(starts)


def test_purge_removes_label_horizon_overlap() -> None:
    """Structural invariant: no training sample's label overlaps the test block.

    The label at ``i`` depends on the window ``[i, i+horizon]``. For every training ``i``:
    either ``i + horizon < test_start`` (left purge), or ``i > test_end`` (the label lies
    entirely after the test block). A leaking splitter would violate this assertion.
    """
    for train, test in _folds():
        t0, t1 = int(test[0]), int(test[-1])
        for i in train.tolist():
            assert (i + HORIZON < t0) or (i > t1)


def test_embargo_gap_after_test() -> None:
    for train, test in _folds():
        t1 = int(test[-1])
        forbidden = set(range(t1 + 1, t1 + 1 + EMBARGO))
        assert forbidden.isdisjoint(train.tolist())


def test_default_embargo_purges_the_right_edge_too() -> None:
    """Regression: every other test in this module passes ``embargo=`` explicitly (the
    ``_folds()`` fixture always does), so none of them exercise the constructor's actual
    default. Before the fix, the default was 0: purge only guards the *left* edge of the
    test block (label-horizon overlap), leaving the training samples immediately after the
    test block (serial-correlation leakage) completely unprotected unless a caller
    remembered to pass embargo explicitly. This must fail red against ``embargo=0``.
    """
    horizon = HORIZON
    splitter = PurgedKFold(n_splits=5, horizon=horizon)  # embargo omitted -> must default to horizon
    assert splitter.embargo == horizon
    for train, test in splitter.split(N_SAMPLES):
        t1 = int(test[-1])
        forbidden = set(range(t1 + 1, t1 + 1 + horizon))
        assert forbidden.isdisjoint(train.tolist())


def test_split_is_deterministic() -> None:
    first = _folds()
    second = _folds()
    for (tr1, te1), (tr2, te2) in zip(first, second):
        assert np.array_equal(tr1, tr2)
        assert np.array_equal(te1, te2)


def test_every_sample_is_tested_once() -> None:
    """OOS coverage: each index appears in exactly one test block."""
    tested = np.concatenate([test for _, test in _folds()])
    assert np.array_equal(np.sort(tested), np.arange(N_SAMPLES))


# --- OOS prediction: the decisive anti-leak arbiter --------------------------------


def _make_model() -> XGBoostDirectionModel:
    return XGBoostDirectionModel(random_state=0, n_estimators=40, max_depth=3)


def test_oos_recovers_known_signal(predictable_dataset) -> None:
    x, y = predictable_dataset
    splitter = PurgedKFold(n_splits=5, horizon=1, embargo=0)
    proba = oos_predict(_make_model, x, y, splitter)
    accuracy = float(((proba > 0.5).astype(float) == y).mean())
    assert accuracy > 0.60


def test_oos_finds_no_skill_on_noise(noise_dataset) -> None:
    """Sanity: on pure noise, OOS validation must reveal no alpha."""
    x, y = noise_dataset
    splitter = PurgedKFold(n_splits=5, horizon=1, embargo=0)
    proba = oos_predict(_make_model, x, y, splitter)
    accuracy = float(((proba > 0.5).astype(float) == y).mean())
    assert 0.43 < accuracy < 0.57


# --- Deflated Sharpe: anti multiple-testing ----------------------------------------


def test_expected_max_sharpe_grows_with_trials() -> None:
    var = 0.5
    assert expected_max_sharpe(1000, var) > expected_max_sharpe(10, var) > 0.0


def test_deflated_sharpe_decreases_with_more_trials() -> None:
    def dsr(n_trials: int) -> float:
        return deflated_sharpe_ratio(1.5, n_obs=1000, n_trials=n_trials, sr_variance=0.25)

    assert dsr(1) > dsr(100) > dsr(10_000)


def test_deflated_sharpe_is_a_probability() -> None:
    dsr = deflated_sharpe_ratio(2.0, n_obs=500, n_trials=50, sr_variance=0.3)
    assert 0.0 <= dsr <= 1.0


def test_negative_sharpe_is_strongly_deflated() -> None:
    dsr = deflated_sharpe_ratio(-0.5, n_obs=500, n_trials=50, sr_variance=0.3)
    assert dsr < 0.5


# --- Sharpe standard error / t-stat / CI: printed uncertainty --------------------


def test_sharpe_standard_error_shrinks_with_more_observations() -> None:
    se_small = sharpe_standard_error(2.0, n_obs=100, periods_per_year=252.0)
    se_large = sharpe_standard_error(2.0, n_obs=10_000, periods_per_year=252.0)
    assert se_large < se_small


def test_sharpe_standard_error_rejects_too_few_observations() -> None:

    with pytest.raises(ValueError):
        sharpe_standard_error(1.0, n_obs=1, periods_per_year=252.0)


def test_sharpe_t_stat_is_sharpe_over_standard_error() -> None:
    sharpe, n_obs, ppy = 1.5, 300, 252.0
    t = sharpe_t_stat(sharpe, n_obs, ppy)
    se = sharpe_standard_error(sharpe, n_obs, ppy)
    assert t == pytest.approx(sharpe / se, rel=1e-9)


def test_small_sample_sharpe_is_not_distinguishable_from_zero() -> None:
    """A thin-sample, elevated Sharpe (P02-like: ~441 effective compute observations)
    should have a t-stat well under the ~1.96 threshold for 95% significance."""
    t = sharpe_t_stat(2.98, n_obs=441, periods_per_year=35040.0)
    assert abs(t) < 1.96


def test_confidence_interval_is_centered_on_sharpe() -> None:
    lo, hi = sharpe_confidence_interval(1.0, n_obs=500, periods_per_year=252.0)
    assert lo < 1.0 < hi


def test_confidence_interval_narrows_with_more_observations() -> None:
    lo_small, hi_small = sharpe_confidence_interval(1.0, n_obs=100, periods_per_year=252.0)
    lo_large, hi_large = sharpe_confidence_interval(1.0, n_obs=10_000, periods_per_year=252.0)
    assert (hi_large - lo_large) < (hi_small - lo_small)
