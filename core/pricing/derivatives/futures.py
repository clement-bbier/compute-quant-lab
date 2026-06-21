"""Cotation et orchestrateur du pricing de futures compute (théorique / SIMULÉ).

:class:`FuturesQuote` porte un champ ``simulated`` **obligatoire** (sans valeur par
défaut) : la frontière réel/simulé est garantie par le type, pas par une convention.
:class:`CarryFuturesPricer` injecte une forward (via ``CarryModel``) et infère
*systématiquement* le convenience yield implicite — ce qui unifie le pricing carry
exogène et l'usage de la courbe Schwartz simulée de P04 sous une seule logique.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.pricing.derivatives.carry import (
    DEFAULT_RISK_FREE_RATE,
    CarrySensitivities,
    carry_sensitivities,
    implied_convenience_yield,
)
from core.pricing.derivatives.protocols import CarryModel


@dataclass(frozen=True)
class FuturesQuote:
    """Cotation théorique d'un future compute pour une maturité donnée.

    ``simulated`` est **obligatoire** (sans défaut) : les futures compute (settlement
    SDH100RT) ne sont pas listés, aucune cotation ne peut « oublier » qu'elle est
    théorique. Unités : prix en $/GPU·h, ``maturity_years`` en années, taux annualisés.
    """

    spot: float
    forward: float
    maturity_years: float
    basis: float  # F − S, la base spot/forward
    rate: float
    convenience_yield: float  # implicite, inféré de la forward
    model_name: str
    sensitivities: CarrySensitivities
    simulated: bool


class CarryFuturesPricer:
    """Price un future compute théorique à partir d'une forward injectée.

    Parameters
    ----------
    model : CarryModel
        Source de forward (portage analytique ou adapter de la forward P04).
    rate : float
        Taux de financement annualisé ``r`` servant à inverser la forward
        (convenience yield implicite) et à calculer les sensibilités.

    Le yield étant inféré de la forward fournie, le pricer redonne le ``y`` exogène
    pour un :class:`CostOfCarryModel` (round-trip) et *extrait* le ``y`` implicite
    d'une forward Schwartz simulée.
    """

    def __init__(self, model: CarryModel, rate: float = DEFAULT_RISK_FREE_RATE) -> None:
        self._model = model
        self._rate = rate

    def price(self, spot: float, tau_years: float) -> FuturesQuote:
        """Cote le future : forward → base → yield implicite → sensibilités."""
        forward = self._model.forward(spot, tau_years)
        convenience_yield = implied_convenience_yield(spot, forward, self._rate, tau_years)
        sensitivities = carry_sensitivities(spot, self._rate, convenience_yield, tau_years)
        return FuturesQuote(
            spot=spot,
            forward=forward,
            maturity_years=tau_years,
            basis=forward - spot,
            rate=self._rate,
            convenience_yield=convenience_yield,
            model_name=self._model.name,
            sensitivities=sensitivities,
            simulated=self._model.simulated,
        )
