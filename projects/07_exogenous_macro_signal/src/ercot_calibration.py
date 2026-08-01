"""Calibration L0 §7 — assembles purged CV (P09) + label + baseline + eval.

For each spec (label x threshold pair from the L0 budget): predicts the spike
**out of sample** (purged K-fold + embargo from `core.models.validation`), compares
the model's PR-AUC to that of the climatology baseline (also out of sample),
and decides via bootstrap CI + Benjamini-Hochberg correction over the spec budget.

Storage-agnostic: takes a panel of predictors ``x`` and labels as input
(supplied from the versioned cold store at run time, cf. rule training-cold-store). The
model is **injectable** (default: logistic regression); the predictors (reserve
margin level, net-load gradient) are columns of ``x``.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from core.models.protocols import FloatArray, Model
from core.models.validation import PurgedKFold, oos_predict
from ercot_baseline import ClimatologyBaseline
from ercot_eval import beats_baseline, benjamini_hochberg


class LogisticModel:
    """Default directional model (logistic regression), conforming to `Model`."""

    def __init__(self) -> None:
        self._clf = LogisticRegression(max_iter=1000)

    def fit(self, x: FloatArray, y: FloatArray) -> LogisticModel:
        self._clf.fit(x, y)
        return self

    def predict_proba(self, x: FloatArray) -> FloatArray:
        return self._clf.predict_proba(x)[:, 1].astype(np.float64)


def oos_baseline_predict(
    y: FloatArray, index: pd.DatetimeIndex, splitter: PurgedKFold
) -> FloatArray:
    """**Out-of-sample** climatology baseline: fitted on train, predicts test."""
    proba = np.full(len(y), np.nan, dtype=np.float64)
    for train, test in splitter.split(len(y)):
        baseline = ClimatologyBaseline.fit(pd.Series(y[train], index=index[train]))
        proba[test] = baseline.predict(index[test])
    return proba


def run_spec(
    x: FloatArray,
    y: FloatArray,
    index: pd.DatetimeIndex,
    *,
    model_factory: Callable[[], Model] = LogisticModel,
    splitter: PurgedKFold | None = None,
    n_boot: int = 1000,
    seed: int = 0,
) -> dict[str, float | bool]:
    """One spec: model's OOS PR-AUC vs OOS climatology baseline (purged + embargo)."""
    splitter = splitter or PurgedKFold(n_splits=5, horizon=1, embargo=0)
    proba_model = oos_predict(model_factory, x, y, splitter)
    proba_base = oos_baseline_predict(y, index, splitter)
    mask = ~np.isnan(proba_model) & ~np.isnan(proba_base)
    return beats_baseline(y[mask], proba_model[mask], proba_base[mask], n_boot=n_boot, seed=seed)


def run_calibration(
    x: FloatArray,
    index: pd.DatetimeIndex,
    label_specs: dict[str, FloatArray],
    *,
    model_factory: Callable[[], Model] = LogisticModel,
    splitter: PurgedKFold | None = None,
    alpha: float = 0.05,
    n_boot: int = 1000,
    seed: int = 0,
) -> dict[str, dict[str, float | bool]]:
    """L0 §7 multi-spec calibration: per-spec "does it beat the baseline?" + BH correction.

    ``label_specs``: spec name -> label vector (0/1). The Benjamini-Hochberg
    correction is applied to the p-values of the differences (L0 spec budget).
    Each result gets ``bh_significant`` (true = retained after FDR control).
    """
    results = {
        name: run_spec(
            x, y, index, model_factory=model_factory, splitter=splitter, n_boot=n_boot, seed=seed
        )
        for name, y in label_specs.items()
    }
    names = list(label_specs)
    rejects = benjamini_hochberg([float(results[n]["p_value"]) for n in names], alpha=alpha)
    for name, rej in zip(names, rejects, strict=True):
        results[name]["bh_significant"] = rej
    return results
