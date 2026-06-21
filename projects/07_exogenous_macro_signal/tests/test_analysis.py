"""Mesure du lead (cross-corrélation + OLS de confirmation) — fixtures connues.

On vérifie que la mécanique *retrouve* un lead injecté volontairement : si la cible
dépend de la feature retardée de ``LEAD``, la cross-corrélation doit culminer en
``k = LEAD`` et l'OLS de confirmation doit avoir un R² out-of-sample élevé.
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
    # cible(t) = 2 * feature(t - lead)  → feature MÈNE la cible de `lead`.
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
