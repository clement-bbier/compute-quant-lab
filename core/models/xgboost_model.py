"""Modèle directionnel XGBoost (baseline PoC) + ensemble de graines.

`XGBoostDirectionModel` enveloppe ``XGBClassifier`` dans une configuration **déterministe**
(graine fixée, mono-thread, ``tree_method="hist"``, pas de sous-échantillonnage aléatoire) :
même entrée ⇒ mêmes probabilités, exigence de reproductibilité du labo.

`SeedBaggingEnsemble` moyenne les probabilités de plusieurs `XGBoostDirectionModel`
identiques à la graine près. C'est l'« ensemble » du PoC : il réduit la variance liée à la
graine (un seul modèle peut sur-ajuster une réalisation), pour un coût marginal. Le palier
institutionnel (LSTM/TFT, stacking) viendra plus tard, mais l'interface `Model` le permet déjà.
"""

from __future__ import annotations

from typing import Callable

import numpy as np
from xgboost import XGBClassifier

from core.models.protocols import FloatArray, Model


class XGBoostDirectionModel:
    """Classifieur directionnel XGBoost déterministe (implémente `Model`).

    Parameters
    ----------
    random_state
        Graine — fixe tout l'aléatoire interne (reproductibilité).
    n_estimators, max_depth, learning_rate, subsample, colsample_bytree
        Hyperparamètres de l'arbre boosté (fixés *a priori* au PoC : pas de recherche,
        donc pas de coût de multiple-testing — cf. ``deflated_sharpe``).
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
            n_jobs=1,  # mono-thread : indispensable au déterminisme bit-à-bit
            tree_method="hist",
            objective="binary:logistic",
            eval_metric="logloss",
            verbosity=0,
        )
        self._clf.fit(x, y.astype(int))
        return self

    def predict_proba(self, x: FloatArray) -> FloatArray:
        if self._clf is None:
            raise RuntimeError("fit() doit être appelé avant predict_proba().")
        return self._clf.predict_proba(x)[:, 1].astype(np.float64)


class SeedBaggingEnsemble:
    """Moyenne des probabilités de modèles identiques à la graine près (implémente `Model`).

    Parameters
    ----------
    make_model
        Fabrique un `Model` neuf à partir d'une graine.
    seeds
        Graines des membres (au moins une). Fixées → ensemble reproductible.

    Raises
    ------
    ValueError
        Si ``seeds`` est vide.
    """

    def __init__(self, *, make_model: Callable[[int], Model], seeds: tuple[int, ...]) -> None:
        if not seeds:
            raise ValueError("seeds ne peut pas être vide.")
        self._make_model = make_model
        self._seeds = seeds
        self._members: list[Model] = []

    def fit(self, x: FloatArray, y: FloatArray) -> "SeedBaggingEnsemble":
        self._members = [self._make_model(seed).fit(x, y) for seed in self._seeds]
        return self

    def predict_proba(self, x: FloatArray) -> FloatArray:
        if not self._members:
            raise RuntimeError("fit() doit être appelé avant predict_proba().")
        stacked = np.stack([member.predict_proba(x) for member in self._members])
        return stacked.mean(axis=0).astype(np.float64)


__all__ = ["XGBoostDirectionModel", "SeedBaggingEnsemble"]
