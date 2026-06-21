"""Contrats de la couche signaux (fondation réutilisable — SOLID / Dependency Inversion).

``core.signals`` promeut les *producteurs de signaux réutilisables* (mean-reversion P02,
basis futures P06, ML P09) derrière une interface commune. Le desk P10 — et tout futur
optimiseur — dépend de ce ``Protocol``, jamais d'une implémentation concrète (DIP / OCP) :
brancher un nouveau signal ne change pas le consommateur.

Compatibilité P08 : ``signal(view) -> float`` est exactement la signature du ``Strategy``
Protocol de ``core.backtest`` — un producteur est donc **directement backtestable** par le
moteur. La sortie est une **vue directionnelle normalisée** dans ``[-1, 1]`` (pas une position
finale : le desk décide de la taille via sa pondération sous risque).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from core.backtest.protocols import PointInTimeView


@dataclass(frozen=True)
class SignalProvenance:
    """Origine d'un signal : réel vs simulé. ``simulated`` est **obligatoire** (sans défaut).

    Frontière réel/simulé non négociable (rule ``forward-real-simulated``) : impossible
    d'oublier d'étiqueter un signal — un test échoue si le drapeau manque.
    """

    name: str
    simulated: bool


@runtime_checkable
class SignalProducer(Protocol):
    """Source d'un signal directionnel point-in-time, étiquetée par sa provenance.

    À chaque instant ``t``, rend une vue directionnelle ``s ∈ [-1, 1]`` à partir de données
    ``≤ t`` (consomme la ``PointInTimeView`` / ``GuardedView`` de P08). Compatible ``Strategy``.
    """

    name: str
    provenance: SignalProvenance

    def signal(self, view: PointInTimeView) -> float: ...


def clip_unit(value: float) -> float:
    """Écrête une vue directionnelle à l'intervalle ``[-1, 1]``."""
    return max(-1.0, min(1.0, value))


__all__ = ["SignalProvenance", "SignalProducer", "clip_unit"]
