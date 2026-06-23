"""Baseline climatologique ERCOT (fiche L0 §7) — le « truc à battre ».

Taux de base des spikes par (heure-de-jour × mois). Un signal n'est retenu que s'il
**dépasse** cette saisonnalité naïve (sinon il ne fait que redécouvrir que les
après-midi d'été sont tendus). Fonctions pures, ajustées sur le fold d'entraînement.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ClimatologyBaseline:
    """Taux de base de spike par (heure-de-jour, mois), + repli global.

    Ajusté sur les labels d'entraînement ; prédit une probabilité par timestamp.
    """

    rates: dict[tuple[int, int], float]
    global_rate: float

    @classmethod
    def fit(cls, labels: pd.Series) -> ClimatologyBaseline:
        """Ajuste le taux de base par (heure, mois) sur ``labels`` (bool/0-1, index UTC)."""
        if labels.index.tz is None:
            raise ValueError("index UTC tz-aware obligatoire")
        frame = pd.DataFrame(
            {
                "y": labels.to_numpy(dtype=float),
                "hour": np.asarray(labels.index.hour),
                "month": np.asarray(labels.index.month),
            }
        )
        rates = frame.groupby(["hour", "month"])["y"].mean().to_dict()
        return cls(rates=dict(rates), global_rate=float(frame["y"].mean()))

    def predict(self, index: pd.DatetimeIndex) -> np.ndarray:
        """Probabilité de spike par timestamp : taux (heure, mois), repli global si inconnu."""
        return np.array(
            [self.rates.get((t.hour, t.month), self.global_rate) for t in index],
            dtype=float,
        )
