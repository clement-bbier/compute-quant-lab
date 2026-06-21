"""Contrats (abstractions) des features exogènes point-in-time.

Le `PointInTimeFeatureBuilder` dépend de ces `Protocol`, jamais d'implémentations
concrètes (Dependency Inversion Principle) : toute source de données exogènes
(gaz, météo, capacity…) interchangeable se conforme au contrat `ExogenousSource`,
ce qui rend les builders testables avec des fixtures et substituables.

Modèle de données — le frame *vintage*
--------------------------------------
Une observation macro porte **deux** horodatages, jamais un seul :

* ``value_ts``      — la période que le chiffre décrit (« HDD du jour D ») ;
* ``knowledge_ts``  — l'instant où le chiffre devient *connu* (publié) ;
                      ``knowledge_ts = value_ts + lag de publication``.

Une révision est simplement une nouvelle ligne avec le même ``value_ts`` mais un
``knowledge_ts`` plus tardif. À l'instant de décision ``t`` on ne voit que les
lignes dont ``knowledge_ts <= t`` — et, par ``value_ts``, la plus récente d'entre
elles. C'est la seule défense correcte contre le look-ahead sur données macro.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np
import numpy.typing as npt
import pandas as pd

#: Tableau de flottants 64 bits (même convention que `core.pricing`).
FloatArray = npt.NDArray[np.float64]

#: Colonnes canoniques d'un frame *vintage* (tidy, long-form).
VALUE_TS = "value_ts"
KNOWLEDGE_TS = "knowledge_ts"
VALUE = "value"
VINTAGE_COLUMNS = (VALUE_TS, KNOWLEDGE_TS, VALUE)


@runtime_checkable
class ExogenousSource(Protocol):
    """Source de variables exogènes, exposées en *vintages* point-in-time.

    Chaque variable est servie comme un frame long-form aux colonnes
    ``(value_ts, knowledge_ts, value)`` (index ignoré), horodatages UTC
    tz-aware. La source ne masque jamais le ``knowledge_ts`` : c'est l'appelant
    (le builder) qui décide ce qui est connu à ``t``.
    """

    def names(self) -> list[str]:
        """Noms des variables exogènes disponibles."""
        ...

    def vintages(self, name: str) -> pd.DataFrame:
        """Frame vintage de ``name`` : colonnes ``(value_ts, knowledge_ts, value)``."""
        ...


@runtime_checkable
class FeatureBuilder(Protocol):
    """Construit des features **point-in-time** : à ``asof``, rien de ``> asof``."""

    def build_asof(self, asof: pd.Timestamp) -> pd.Series:
        """Vecteur de features connu à l'instant de décision ``asof``."""
        ...

    def build_panel(self, decision_index: pd.DatetimeIndex) -> pd.DataFrame:
        """Panel (une ligne par instant de décision), toutes features ``<= t``."""
        ...
