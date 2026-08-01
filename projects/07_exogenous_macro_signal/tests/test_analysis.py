"""Lead measurement (cross-correlation + confirmation OLS) — known fixtures.

Verifies that the mechanism *recovers* a deliberately injected lead: if the target
depends on the feature delayed by ``LEAD``, the cross-correlation must peak at
``k = LEAD`` and the confirmation OLS must have a high out-of-sample R².
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import analysis


def _index(n: int) -> pd.DatetimeIndex:
    return pd.date_range("2025-01-01", periods=n, freq="D", tz="UTC")


def test_cross_correlation_recovers_injected_lead():
    rng = np.random.default_rng(0)
    n, lead = 200, 3
    idx = _index(n)
    feature = pd.Series(rng.normal(size=n), index=idx)
    # target(t) = 2 * feature(t - lead)  -> feature LEADS the target by `lead`.
    target = 2.0 * feature.shift(lead)

    corr = analysis.cross_correlations(feature, target, max_lag=6)
    assert list(corr.index) == list(range(7))
    assert analysis.best_lag(corr) == lead
    assert abs(corr.loc[lead]) > 0.99


def test_confirm_ols_reports_high_oos_r2_on_linear_link():
    rng = np.random.default_rng(1)
    n, lead = 200, 2
    idx = _index(n)
    feature = pd.Series(rng.normal(size=n), index=idx)
    target = 1.5 * feature.shift(lead) + rng.normal(scale=0.01, size=n)

    stats = analysis.confirm_ols(feature, target, lag=lead, train_frac=0.7)
    assert stats["r2_oos"] > 0.95
    assert abs(stats["coef"] - 1.5) < 0.1
    assert stats["n_test"] > 0
