"""Signal directionnel ML hors-échantillon (enveloppe l'adaptateur P09).

Le producteur **délègue** à ``PrecomputedSignalStrategy`` de ``core.models`` (P09) : un vecteur de
probabilités ``P(montée)`` hors-échantillon (purged-CV, cf. ``core.models.validation.oos_predict``)
est calculé **en amont** et aligné 1:1 sur la série backtestée ; au runtime, l'adaptateur lit la
proba à ``view.t`` et la mappe en position (bande neutre autour de 0.5). Le modèle ne « voit »
jamais les prix au runtime — toute fuite éventuelle a été neutralisée à l'entraînement.

On n'ajoute donc **aucune** logique de signal ici : parité exacte avec P09 garantie par délégation
(§6b). Ce module n'apporte que l'habillage ``SignalProducer`` (nom + provenance réel/simulé).
"""

from __future__ import annotations

from core.backtest.protocols import PointInTimeView
from core.models.protocols import FloatArray
from core.models.strategy import PrecomputedSignalStrategy
from core.signals.protocols import SignalProvenance


class MLEnsembleSignal:
    """Enveloppe ``SignalProducer`` autour de l'adaptateur ML pré-calculé de P09.

    Parameters
    ----------
    proba : FloatArray
        Vecteur ``P(montée)`` OOS aligné sur la série backtestée (``NaN`` ⇒ position plate).
    neutral_band : float
        Demi-largeur de la bande morte autour de 0.5 (``[0, 0.5)``), transmise telle quelle à P09.
    name : str
        Identifiant du signal (tracé MLflow / attribution desk).
    simulated : bool
        Drapeau réel/simulé **obligatoire** (rule ``forward-real-simulated``).
    """

    def __init__(
        self,
        proba: FloatArray,
        *,
        neutral_band: float = 0.0,
        name: str = "ml_ensemble",
        simulated: bool,
    ) -> None:
        # Validation (bande neutre) et logique proba→position héritées telles quelles de P09.
        self._strategy = PrecomputedSignalStrategy(proba, neutral_band=neutral_band)
        self.name = name
        self.provenance = SignalProvenance(name=name, simulated=simulated)

    def signal(self, view: PointInTimeView) -> float:
        """Position cible à ``view.t`` : délègue à l'adaptateur P09 (parité exacte)."""
        return self._strategy.signal(view)


__all__ = ["MLEnsembleSignal"]
