"""Contrats (abstractions) du pricing de futures compute théoriques.

Le :class:`~core.pricing.derivatives.futures.CarryFuturesPricer` dépend de ces
``Protocol``, jamais d'une implémentation concrète (Dependency Inversion Principle).
Toute source de forward — modèle de portage analytique (:class:`CostOfCarryModel`)
ou adapter de la courbe Schwartz **simulée** de P04 — se conforme à ``CarryModel``,
ce qui rend le pricer testable avec des mocks et la forward injectable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from core.pricing.derivatives.futures import FuturesQuote


@runtime_checkable
class CarryModel(Protocol):
    """Stratégie productrice d'un prix forward théorique à partir du spot.

    Frontière réel/simulé : ``simulated`` fait partie du contrat. Les futures
    compute n'étant pas listés, toute forward produite ici est simulée.
    """

    @property
    def name(self) -> str:
        """Identifiant du modèle (tracé MLflow)."""
        ...

    @property
    def simulated(self) -> bool:
        """``True`` si la forward est simulée/théorique (jamais un prix de marché)."""
        ...

    def forward(self, spot: float, tau_years: float) -> float:
        """Prix forward en $/GPU·h pour une maturité ``tau_years`` (années)."""
        ...


@runtime_checkable
class FuturesPricer(Protocol):
    """Orchestrateur : price un future compute théorique en ``FuturesQuote``."""

    def price(self, spot: float, tau_years: float) -> FuturesQuote:
        """Cote le future à partir du spot et de la maturité (cotation simulée)."""
        ...
