"""Temporal validation: purged k-fold + embargo, leak-free OOS, deflated Sharpe.

Heart of the anti-overfitting defense (Lopez de Prado). The tests prove the absence of
train/test overlap *at the level of the label horizon* (not only of the indices), and that
the Deflated Sharpe does penalize multiple-testing.
"""

from __future__ import annotations

import numpy as np

from core.models.validation import (
    PurgedKFold,
    deflated_sharpe_ratio,
    expected_max_sharpe,
    oos_predict,
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
