"""Calibration L0 §7 — assemble purged CV (P09) + label + baseline + éval.

Pour chaque spec (couple label × seuil du budget L0) : on prédit le spike **hors
échantillon** (purged K-fold + embargo de `core.models.validation`), on compare la
PR-AUC du modèle à celle de la baseline climatologique (elle aussi hors échantillon),
et on tranche par IC bootstrap + correction Benjamini-Hochberg sur le budget de specs.

Storage-agnostique : prend un panel de prédicteurs ``x`` et des labels en entrée
(fournis depuis le cold store versionné au run, cf. rule training-cold-store). Le
modèle est **injectable** (défaut : régression logistique) ; les prédicteurs (niveau
de marge de réserve, gradient net-load) sont des colonnes de ``x``.
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
    """Modèle directionnel par défaut (régression logistique), conforme à `Model`."""

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
    """Baseline climatologique **hors-échantillon** : ajustée sur le train, prédit le test."""
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
    """Une spec : PR-AUC OOS du modèle vs baseline climatologique OOS (purged + embargo)."""
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
    """Calibration multi-specs L0 §7 : par spec « bat-il la baseline ? » + correction BH.

    ``label_specs`` : nom de spec -> vecteur de labels (0/1). La correction
    Benjamini-Hochberg s'applique sur les p-values des différences (budget de specs L0).
    Chaque résultat reçoit ``bh_significant`` (vrai = retenu après contrôle du FDR).
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
