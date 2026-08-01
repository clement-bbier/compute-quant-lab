"""Measures the *lead* of an exogenous feature over the spread target (anti-overfit).

Two complementary tools, deliberately simple (the brief requires "no
overfitting"):

* `cross_correlations` — correlation of feature(t) vs target(t+k) for k = 0..K.
  Transparent, robust, model-free. Gives the optimal lag.
* `confirm_ols` — confirmation regression at the optimal lag, **strict temporal
  split** (no shuffling, cf. rule no-look-ahead) and out-of-sample R².

Pure functions (no I/O): testable on known fixtures.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import statsmodels.api as sm


def cross_correlations(
    feature: pd.Series,
    target: pd.Series,
    max_lag: int,
    method: str = "pearson",
) -> pd.Series:
    """Correlation of ``feature(t)`` with ``target(t + k)`` for ``k = 0..max_lag``.

    A positive ``k`` where the correlation peaks means the feature **leads**
    the target by ``k`` steps (predictive power / lead).
    """
    correlations: dict[int, float] = {}
    for k in range(max_lag + 1):
        pair = pd.concat([feature, target.shift(-k)], axis=1).dropna()
        correlations[k] = (
            float(pair.iloc[:, 0].corr(pair.iloc[:, 1], method=method))
            if len(pair) >= 3
            else float("nan")
        )
    return pd.Series(correlations, name=f"xcorr_{method}")


def best_lag(corr: pd.Series) -> int:
    """Lag of maximum absolute correlation (the strongest lead)."""
    return int(corr.abs().idxmax())


def confirm_ols(
    feature: pd.Series,
    target: pd.Series,
    lag: int,
    train_frac: float = 0.7,
) -> dict[str, Any]:
    """Confirmation OLS ``target(t+lag) ~ feature(t)`` with a strict temporal split.

    The split is chronological (the first ``train_frac`` observations are used
    for training, the rest for testing): no train->test leakage on the time
    series. Returns coefficient, p-value, and in-sample / out-of-sample R².
    """
    aligned = pd.concat([feature.rename("x"), target.shift(-lag).rename("y")], axis=1).dropna()
    n_train = int(len(aligned) * train_frac)
    train, test = aligned.iloc[:n_train], aligned.iloc[n_train:]

    model = sm.OLS(train["y"], sm.add_constant(train["x"])).fit()
    pred = model.predict(sm.add_constant(test["x"], has_constant="add"))
    ss_res = float(((test["y"] - pred) ** 2).sum())
    ss_tot = float(((test["y"] - test["y"].mean()) ** 2).sum())
    r2_oos = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")

    return {
        "lag": int(lag),
        "coef": float(model.params["x"]),
        "intercept": float(model.params["const"]),
        "pvalue": float(model.pvalues["x"]),
        "r2_in": float(model.rsquared),
        "r2_oos": float(r2_oos),
        "n_train": int(len(train)),
        "n_test": int(len(test)),
    }
