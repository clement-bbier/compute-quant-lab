"""Frontière public / edge — le **point d'injection unique** du produit.

Le produit public consomme un :class:`SignalSource` *injecté*. L'implémentation par
défaut (:class:`NaiveSignalSource`) est une **heuristique triviale, sans edge** : elle ne
fait que regarder la mesure du moment. Le vrai **timing calibré** (l'edge monétisable)
vit dans ``private/`` (WP) et substitue ce ``SignalSource`` *localement*, **jamais
committé**. Comme le produit ne dépend que du Protocol, il est structurellement
impossible de fuiter l'edge en clair (mypy garde la frontière).

Discipline réel/simulé empruntée à ``core.signals`` (rule ``forward-real-simulated``)
mais **découplée** : la couche produit ne tire pas le moteur de backtest (noyau Rust).
Ici ``simulated=True`` signifie « recommandation heuristique non-edge » — le free tier
n'est jamais pris pour un signal validé. Une impl edge calibrée porterait ``simulated=False``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable

from views import MarketView


class Action(Enum):
    """Recommandation de procurement (le « quoi faire maintenant »)."""

    WAIT = "wait"
    RENT_NOW = "rent_now"


@dataclass(frozen=True)
class SignalProvenance:
    """Origine d'une recommandation. ``simulated`` est **obligatoire** (sans défaut).

    Impossible d'oublier d'étiqueter une recommandation : la construire sans le drapeau
    lève ``TypeError`` (un test le garantit). ``simulated=True`` ⇔ heuristique non-edge.
    """

    name: str
    simulated: bool


@dataclass(frozen=True)
class ProcurementSignal:
    """Recommandation point-in-time servie par un :class:`SignalSource`.

    ``action`` est la décision ; ``venue``/``reference_price`` situent la meilleure offre
    *mesurée* ; ``rationale`` explicite la raison (auditable) ; ``provenance`` étiquette
    l'origine (edge vs heuristique).
    """

    action: Action
    gpu_model: str
    venue: str
    reference_price: float
    rationale: str
    provenance: SignalProvenance


@runtime_checkable
class SignalSource(Protocol):
    """Source d'une recommandation de procurement — **le point d'injection**.

    Une seule méthode : à partir d'une :class:`~views.MarketView` point-in-time, rendre
    une :class:`ProcurementSignal`. L'impl publique est naïve ; l'edge privé la substitue.
    """

    name: str

    def assess(self, market: MarketView) -> ProcurementSignal: ...


@dataclass(frozen=True)
class NaiveSignalSource:
    """Impl publique par défaut — heuristique triviale, **aucun edge**.

    ``RENT_NOW`` ssi la venue la moins chère est *strictement* sous la médiane inter-venues
    (il existe un vrai écart à capter) ; sinon ``WAIT`` (pas d'écart → rien d'urgent). Aucun
    seuil calibré, aucune information de timing : le vrai edge vit dans ``private/`` (WP).
    """

    name: str = "naive_public"

    def assess(self, market: MarketView) -> ProcurementSignal:
        cheapest = market.cheapest
        has_spread = cheapest.rate < market.median_rate
        action = Action.RENT_NOW if has_spread else Action.WAIT
        rationale = (
            f"heuristique publique : {cheapest.source} à {cheapest.rate:.2f} $/GPU·h "
            f"{'sous' if has_spread else 'au niveau de'} la médiane inter-venues "
            f"({market.median_rate:.2f}). Timing calibré = premium (edge privé)."
        )
        return ProcurementSignal(
            action=action,
            gpu_model=market.gpu_model,
            venue=cheapest.source,
            reference_price=cheapest.rate,
            rationale=rationale,
            provenance=SignalProvenance(name=self.name, simulated=True),
        )
