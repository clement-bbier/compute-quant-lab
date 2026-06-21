"""Construction de la matrice de features et de la cible directionnelle (point-in-time).

`build_labels` encode la **direction future** du spread (cible binaire). `FeaturePipeline`
assemble deux sources de features, toutes causales (``<= t``) :

* features dérivées du spread lui-même (lags, moyennes glissantes, momentum) — causales par
  construction (``shift`` positif, ``rolling`` arrière) ;
* features exogènes point-in-time de **P07** (`core.features`), si un builder est injecté :
  à ``t``, seules les observations dont le ``knowledge_ts <= t`` entrent (lags de publication
  + révisions gérés en amont).

La cible n'est JAMAIS une feature : `build_labels` regarde ``t+horizon`` (le futur), ce qui
en fait un label d'entraînement, jamais une entrée du modèle à l'inférence.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from core.features.protocols import FeatureBuilder


def build_labels(spread: pd.Series, *, horizon: int) -> pd.Series:
    """Cible directionnelle : ``1`` si le spread monte sur ``horizon`` pas, ``0`` sinon.

    Les ``horizon`` dernières lignes n'ont pas de futur observable → ``NaN`` (exclues de
    l'entraînement). C'est la seule façon honnête de borner l'apprentissage.
    """
    if horizon < 1:
        raise ValueError(f"horizon ({horizon}) doit être >= 1.")
    forward_move = spread.shift(-horizon) - spread
    direction = (forward_move > 0.0).astype(float)
    direction[forward_move.isna()] = np.nan
    direction.name = "direction"
    return direction


@dataclass(frozen=True)
class SpreadFeatureSpec:
    """Transforms causales à dériver du spread (toutes ``<= t`` par construction)."""

    lags: tuple[int, ...] = ()
    rolling_means: tuple[int, ...] = ()
    momentums: tuple[int, ...] = field(default=())


class FeaturePipeline:
    """Assemble une matrice de features point-in-time (spread + exogènes P07).

    Parameters
    ----------
    spread_spec
        Quelles features dériver du spread.
    exog_builder
        Builder point-in-time P07 optionnel (`FeatureBuilder`) pour les variables exogènes.
    """

    def __init__(
        self,
        *,
        spread_spec: SpreadFeatureSpec,
        exog_builder: FeatureBuilder | None = None,
    ) -> None:
        self._spread_spec = spread_spec
        self._exog_builder = exog_builder

    def _spread_features(self, spread: pd.Series) -> pd.DataFrame:
        columns: dict[str, pd.Series] = {}
        for k in self._spread_spec.lags:
            columns[f"spread_lag{k}"] = spread.shift(k)
        for w in self._spread_spec.rolling_means:
            columns[f"spread_roll{w}"] = spread.rolling(w).mean()
        for k in self._spread_spec.momentums:
            columns[f"spread_mom{k}"] = spread - spread.shift(k)
        return pd.DataFrame(columns, index=spread.index)

    def build_matrix(self, spread: pd.Series) -> pd.DataFrame:
        """Matrice de features (une ligne par instant de décision = index du spread)."""
        if not isinstance(spread.index, pd.DatetimeIndex):
            raise ValueError("le spread doit être indexé par un DatetimeIndex (point-in-time).")
        matrix = self._spread_features(spread)
        if self._exog_builder is not None:
            exog = self._exog_builder.build_panel(spread.index)
            matrix = pd.concat([matrix, exog], axis=1)
        return matrix


__all__ = ["build_labels", "SpreadFeatureSpec", "FeaturePipeline"]
