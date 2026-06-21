"""Producteurs de signaux réutilisables (fondation du labo).

Promotion *PoC → fondation* : la logique de signal des projets de recherche remonte ici,
derrière une interface commune (`SignalProducer`) compatible avec le moteur de backtest P08.

- `MeanReversionSignal` — retour à la moyenne du spread (z-score à hystérésis, promu de P02).
- `FuturesBasisSignal` — carry/roll de la base future↔spot (sur le cost-of-carry de P06).
- `MLEnsembleSignal` — signal directionnel ML hors-échantillon (enveloppe l'adaptateur P09).
"""

from core.signals.futures_basis import FuturesBasisSignal
from core.signals.mean_reversion import MeanReversionSignal
from core.signals.ml import MLEnsembleSignal
from core.signals.protocols import SignalProducer, SignalProvenance, clip_unit

__all__ = [
    "SignalProducer",
    "SignalProvenance",
    "clip_unit",
    "MeanReversionSignal",
    "FuturesBasisSignal",
    "MLEnsembleSignal",
]
