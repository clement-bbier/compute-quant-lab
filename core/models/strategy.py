"""Adaptateur : signal ML pré-calculé → ``Strategy`` du moteur de backtest P08.

Le moteur P08 ne passe à la stratégie qu'une `PointInTimeView` sur la **série de prix** ;
il ne connaît rien aux features. On découple donc en deux temps : (1) un vecteur de
probabilités hors-échantillon est calculé en amont (purged-CV, cf. `validation.oos_predict`),
aligné 1:1 sur la série backtestée ; (2) cette stratégie mince lit la proba à ``view.t`` et
la mappe en position. Conséquence : le modèle ne « voit » jamais les prix au runtime — toute
fuite éventuelle a été neutralisée en amont, et le garde-fou ``GuardedView`` reste gratuit.

La règle proba→position porte l'unique arbitrage de risque de l'adaptateur (bande neutre).
"""

from __future__ import annotations

import numpy as np

# On vise le sous-module `protocols` (numpy seul), pas `core.backtest` dont l'__init__
# importe le moteur et son noyau Rust : la couche modèle reste ainsi importable et
# testable sans build Rust (le backtest réel, lui, compose l'engine au niveau projet).
from core.backtest.protocols import PointInTimeView
from core.models.protocols import FloatArray

#: Probabilité d'indifférence : 0.5 = le modèle n'a pas d'avis directionnel.
_INDIFFERENCE = 0.5


class PrecomputedSignalStrategy:
    """Mappe une proba OOS pré-calculée en position (implémente le `Strategy` Protocol P08).

    Parameters
    ----------
    proba
        Vecteur ``P(montée)`` aligné sur la série backtestée. ``NaN`` (pas de prédiction
        disponible : warm-up / queue non observable) ⇒ position plate.
    neutral_band
        Demi-largeur de la bande morte autour de 0.5. ``0`` = on prend toujours un côté ;
        plus large = on reste à plat tant que le modèle est incertain (↓ turnover/coûts,
        ↓ exposition). Doit être dans ``[0, 0.5)``.

    Raises
    ------
    ValueError
        Si ``neutral_band`` n'est pas dans ``[0, 0.5)``.
    """

    def __init__(self, proba: FloatArray, *, neutral_band: float = 0.0) -> None:
        if not 0.0 <= neutral_band < 0.5:
            raise ValueError(f"neutral_band ({neutral_band}) doit être dans [0, 0.5).")
        self._proba = np.asarray(proba, dtype=np.float64)
        self._neutral_band = neutral_band

    def _to_position(self, p: float) -> float:
        """Règle proba→position : long au-dessus de la bande, short en-dessous, plat dedans."""
        if p > _INDIFFERENCE + self._neutral_band:
            return 1.0
        if p < _INDIFFERENCE - self._neutral_band:
            return -1.0
        return 0.0

    def signal(self, view: PointInTimeView) -> float:
        """Position cible à ``view.t`` : mappe la proba OOS de cet instant (NaN ⇒ plat)."""
        p = float(self._proba[view.t])
        if np.isnan(p):
            return 0.0
        return self._to_position(p)


__all__ = ["PrecomputedSignalStrategy"]
