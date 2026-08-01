"""XGBoost directional model (PoC baseline) + seed ensemble.

`XGBoostDirectionModel` wraps ``XGBClassifier`` in a **deterministic** configuration (fixed
seed, single-threaded, ``tree_method="hist"``, no random subsampling): same input implies
same probabilities, the lab's reproducibility requirement.

`SeedBaggingEnsemble` averages the probabilities of several `XGBoostDirectionModel` instances
that are identical up to the seed. This is the PoC's "ensemble": it reduces the seed-related
variance (a single model can overfit one realization) at a marginal cost. The institutional
tier (LSTM/TFT, stacking) will come later, but the `Model` interface already allows it.
"""

from __future__ import annotations

from typing import Callable

import numpy as np
from xgboost import XGBClassifier

from core.models.protocols import FloatArray, Model


class XGBoostDirectionModel:
    """Deterministic XGBoost directional classifier (implements `Model`).

    Parameters
    ----------
    random_state
        Seed — fixes all internal randomness (reproducibility).
    n_estimators, max_depth, learning_rate, subsample, colsample_bytree
        Hyperparameters of the boosted tree (fixed *a priori* in the PoC: no search, hence
        no multiple-testing cost — see ``deflated_sharpe``).
    """

    def __init__(
        self,
        *,
        random_state: int = 42,
        n_estimators: int = 200,
        max_depth: int = 4,
        learning_rate: float = 0.05,
        subsample: float = 1.0,
        colsample_bytree: float = 1.0,
    ) -> None:
        self.random_state = random_state
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.learning_rate = learning_rate
        self.subsample = subsample
        self.colsample_bytree = colsample_bytree
        self._clf: XGBClassifier | None = None

    def fit(self, x: FloatArray, y: FloatArray) -> "XGBoostDirectionModel":
        self._clf = XGBClassifier(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            learning_rate=self.learning_rate,
            subsample=self.subsample,
            colsample_bytree=self.colsample_bytree,
            random_state=self.random_state,
            n_jobs=1,  # single-threaded: essential for bit-for-bit determinism
            tree_method="hist",
            objective="binary:logistic",
            eval_metric="logloss",
            verbosity=0,
        )
        self._clf.fit(x, y.astype(int))
        return self

    def predict_proba(self, x: FloatArray) -> FloatArray:
        if self._clf is None:
            raise RuntimeError("fit() must be called before predict_proba().")
        return self._clf.predict_proba(x)[:, 1].astype(np.float64)


class SeedBaggingEnsemble:
    """Average the probabilities of models identical up to the seed (implements `Model`).

    Parameters
    ----------
    make_model
        Builds a fresh `Model` from a seed.
    seeds
        Seeds of the members (at least one). Fixed -> reproducible ensemble.

    Raises
    ------
    ValueError
        If ``seeds`` is empty.
    """

    def __init__(self, *, make_model: Callable[[int], Model], seeds: tuple[int, ...]) -> None:
        if not seeds:
            raise ValueError("seeds must not be empty.")
        self._make_model = make_model
        self._seeds = seeds
        self._members: list[Model] = []

    def fit(self, x: FloatArray, y: FloatArray) -> "SeedBaggingEnsemble":
        self._members = [self._make_model(seed).fit(x, y) for seed in self._seeds]
        return self

    def predict_proba(self, x: FloatArray) -> FloatArray:
        if not self._members:
            raise RuntimeError("fit() must be called before predict_proba().")
        stacked = np.stack([member.predict_proba(x) for member in self._members])
        return stacked.mean(axis=0).astype(np.float64)


__all__ = ["XGBoostDirectionModel", "SeedBaggingEnsemble"]
