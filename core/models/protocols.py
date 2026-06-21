"""Contrats de la couche modèle ML (SOLID / Dependency Inversion).

La validation (`validation.py`) et l'adaptateur de stratégie (`strategy.py`) dépendent
de ces ``Protocol`` — jamais d'une implémentation concrète. Un nouveau modèle (XGBoost
aujourd'hui, LSTM/TFT au palier institutionnel) se conforme au contrat `Model` et devient
utilisable partout sans changer la mécanique de validation (Open/Closed).

Convention de la cible
-----------------------
La cible est **binaire directionnelle** : ``1`` = le spread monte sur l'horizon, ``0`` = il
baisse (cf. `pipeline.build_labels`). Un `Model` expose donc ``predict_proba`` renvoyant la
probabilité ``P(montée)`` par échantillon, dans ``[0, 1]``.
"""

from __future__ import annotations

from typing import Iterator, Protocol, runtime_checkable

import numpy as np
from numpy.typing import NDArray

#: Tableau de flottants 64 bits (même convention que `core.pricing` / `core.backtest`).
FloatArray = NDArray[np.float64]
#: Tableau d'indices entiers (sorties des splitters).
IntArray = NDArray[np.intp]


@runtime_checkable
class Model(Protocol):
    """Classifieur directionnel injectable : ``fit`` puis ``predict_proba`` ∈ [0, 1]."""

    def fit(self, x: FloatArray, y: FloatArray) -> "Model":
        """Entraîne le modèle sur ``(x, y)`` et renvoie ``self`` (chaînage)."""
        ...

    def predict_proba(self, x: FloatArray) -> FloatArray:
        """Probabilité ``P(montée)`` par ligne de ``x`` (vecteur 1-D dans [0, 1])."""
        ...


@runtime_checkable
class Splitter(Protocol):
    """Génère des découpes ``(train_idx, test_idx)`` temporelles (jamais de shuffle)."""

    def split(self, n_samples: int) -> Iterator[tuple[IntArray, IntArray]]:
        """Itère les folds : indices d'entraînement et de test, disjoints."""
        ...


__all__ = ["FloatArray", "IntArray", "Model", "Splitter"]
