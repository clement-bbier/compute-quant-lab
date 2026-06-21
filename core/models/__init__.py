"""Couche modèle ML du labo (couche Stratégie, P09).

Ensemble directionnel sur le spark spread, **backtestable via l'interface `Strategy` de P08**
sans glue : un vecteur de probabilités hors-échantillon (purged-CV) devient un signal de
position. Discipline centrale : la rigueur de validation temporelle (anti-overfitting) prime
sur la complexité du modèle.

Briques réutilisables :
  - `protocols`   : contrats `Model` / `Splitter` (DI).
  - `validation`  : `PurgedKFold` (+embargo), `oos_predict`, `deflated_sharpe_ratio`.
  - `pipeline`    : `FeaturePipeline` (consomme `core.features` P07), `build_labels`.
  - `xgboost_model` : `XGBoostDirectionModel`, `SeedBaggingEnsemble`.
  - `strategy`    : `PrecomputedSignalStrategy` (adaptateur vers `core.backtest`).
"""

from core.models.pipeline import FeaturePipeline, SpreadFeatureSpec, build_labels
from core.models.protocols import FloatArray, IntArray, Model, Splitter
from core.models.strategy import PrecomputedSignalStrategy
from core.models.validation import (
    PurgedKFold,
    deflated_sharpe_ratio,
    expected_max_sharpe,
    oos_predict,
)
from core.models.xgboost_model import SeedBaggingEnsemble, XGBoostDirectionModel

__all__ = [
    # Contrats.
    "Model",
    "Splitter",
    "FloatArray",
    "IntArray",
    # Validation temporelle anti-overfitting.
    "PurgedKFold",
    "oos_predict",
    "expected_max_sharpe",
    "deflated_sharpe_ratio",
    # Features & cible.
    "FeaturePipeline",
    "SpreadFeatureSpec",
    "build_labels",
    # Modèles.
    "XGBoostDirectionModel",
    "SeedBaggingEnsemble",
    # Adaptateur backtest.
    "PrecomputedSignalStrategy",
]
