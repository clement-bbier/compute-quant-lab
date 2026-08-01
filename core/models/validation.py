"""Temporal anti-overfitting validation (Lopez de Prado).

Three building blocks, all serving the project's risk number 1 — overfitting:

* `PurgedKFold` — k-fold **without shuffle**: contiguous test blocks, with *purging* of the
  label horizon (any training sample whose label window overlaps the test set is removed)
  and *embargo* (the samples just after the test set are neutralized, against serial
  correlation). This is the only correct split on financial series.
* `oos_predict` — assembles an **out-of-sample** prediction vector aligned on the input
  rows: each row is predicted by a model that never saw it nor its neighborhood (thanks to
  purge/embargo). This vector is what becomes the backtested signal.
* `deflated_sharpe_ratio` — deflates the observed Sharpe by the number of trials
  (`n_trials`): the more configurations are tested, the more a nice Sharpe arises by chance.

Reference: Advances in Financial Machine Learning (purged CV, embargo, Deflated Sharpe).
"""

from __future__ import annotations

from typing import Callable, Iterator

import numpy as np
from scipy.stats import norm

from core.models.protocols import FloatArray, IntArray, Model

#: Euler-Mascheroni constant (law of the maximum of a Gaussian sample).
_EULER_MASCHERONI = 0.5772156649015329


class PurgedKFold:
    """Purged temporal k-fold + embargo (implements `Splitter`).

    Parameters
    ----------
    n_splits
        Number of folds (contiguous test blocks).
    horizon
        Label horizon (in steps): width of the purge to the left of the test block. A label
        at ``i`` depends on the window ``[i, i+horizon]``; any training sample whose window
        touches the test block is removed.
    embargo
        Number of steps neutralized immediately after each test block.

    Raises
    ------
    ValueError
        If ``n_splits < 2``, ``horizon < 0`` or ``embargo < 0``.
    """

    def __init__(self, *, n_splits: int, horizon: int = 1, embargo: int = 0) -> None:
        if n_splits < 2:
            raise ValueError(f"n_splits ({n_splits}) must be >= 2.")
        if horizon < 0:
            raise ValueError(f"horizon ({horizon}) must be >= 0.")
        if embargo < 0:
            raise ValueError(f"embargo ({embargo}) must be >= 0.")
        self.n_splits = n_splits
        self.horizon = horizon
        self.embargo = embargo

    def split(self, n_samples: int) -> Iterator[tuple[IntArray, IntArray]]:
        """Iterate ``(train_idx, test_idx)``: contiguous test blocks, purged + embargoed train."""
        if n_samples < self.n_splits:
            raise ValueError(f"n_samples ({n_samples}) must be >= n_splits ({self.n_splits}).")
        indices = np.arange(n_samples, dtype=np.intp)
        for test in np.array_split(indices, self.n_splits):
            if test.size == 0:
                continue
            t0, t1 = int(test[0]), int(test[-1])
            mask = np.ones(n_samples, dtype=bool)
            mask[t0 : t1 + 1] = False  # the test block itself
            mask[max(0, t0 - self.horizon) : t0] = False  # purge: label overlapping the test
            mask[t1 + 1 : min(n_samples, t1 + 1 + self.embargo)] = False  # embargo
            yield indices[mask], test


def oos_predict(
    make_model: Callable[[], Model],
    x: FloatArray,
    y: FloatArray,
    splitter: PurgedKFold,
) -> FloatArray:
    """Out-of-sample probabilities aligned on the rows of ``x``.

    For each fold, a **fresh** model (``make_model()``) is trained on the purged training set
    then predicts the test block. No row is ever predicted by a model that has seen it.

    Returns
    -------
    FloatArray
        ``P(up)`` vector of length ``len(x)`` (``NaN`` for a row that was never tested).
    """
    n = x.shape[0]
    proba = np.full(n, np.nan, dtype=np.float64)
    for train, test in splitter.split(n):
        model = make_model()
        model.fit(x[train], y[train])
        proba[test] = model.predict_proba(x[test])
    return proba


def expected_max_sharpe(n_trials: int, sr_variance: float) -> float:
    """Expected maximum Sharpe over ``n_trials`` trials under the null (true SR = 0).

    Approximated by the law of the maximum of a Gaussian sample (Lopez de Prado): the
    threshold to beat **grows** with the number of trials — that is the cost of
    multiple-testing.
    """
    if n_trials < 1:
        raise ValueError(f"n_trials ({n_trials}) must be >= 1.")
    if n_trials == 1:
        return 0.0
    z1 = float(norm.ppf(1.0 - 1.0 / n_trials))
    z2 = float(norm.ppf(1.0 - 1.0 / (n_trials * np.e)))
    return float(np.sqrt(sr_variance) * ((1.0 - _EULER_MASCHERONI) * z1 + _EULER_MASCHERONI * z2))


def deflated_sharpe_ratio(
    observed_sr: float,
    *,
    n_obs: int,
    n_trials: int,
    sr_variance: float,
    skew: float = 0.0,
    kurtosis: float = 3.0,
) -> float:
    """Deflated Sharpe Ratio: probability that the true Sharpe is > 0 **after** deflation.

    The observed Sharpe is compared not to 0 but to the maximum *expected under chance* given
    ``n_trials`` (see `expected_max_sharpe`), then a Probabilistic Sharpe Ratio is computed
    accounting for the non-normality of returns (``skew``, ``kurtosis``).

    Parameters
    ----------
    observed_sr
        Observed Sharpe (same time base as ``n_obs``).
    n_obs
        Number of return observations.
    n_trials
        Number of configurations tried (anti multiple-testing). **To be logged honestly.**
    sr_variance
        Variance of the Sharpe estimates across trials (dispersion of the search).
    skew, kurtosis
        Third and fourth moments of the returns (Gaussian: 0 and 3).

    Returns
    -------
    float
        Probability in ``[0, 1]`` — close to 1 = robust, close to 0 = illusory.
    """
    sr_star = expected_max_sharpe(n_trials, sr_variance)
    denom = np.sqrt(1.0 - skew * observed_sr + (kurtosis - 1.0) / 4.0 * observed_sr**2)
    z = (observed_sr - sr_star) * np.sqrt(n_obs - 1) / denom
    return float(norm.cdf(z))


__all__ = [
    "PurgedKFold",
    "oos_predict",
    "expected_max_sharpe",
    "deflated_sharpe_ratio",
]
