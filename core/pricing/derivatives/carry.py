"""Cœur cost-of-carry du pricing de futures compute (théorique / SIMULÉ).

Modèle de portage : ``F = S·e^{(r−y)τ}`` où ``r`` est le taux de financement
annualisé, ``y`` le convenience yield annualisé (non observable → hypothèse ou
*inféré* depuis une forward) et ``τ`` la maturité en années. Propriété de
convergence : ``F(τ=0) = S``. Report (contango) si ``r > y``, déport
(backwardation) si ``y > r``.

Fonctions pures (rule python-quality) : aucun I/O, aucune dépendance à ``projects/``.
Unités : ``spot``/``forward`` en $/GPU·h ; ``rate``/``convenience_yield`` annualisés.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

#: Taux de financement annualisé par défaut (hypothèse PoC, documentée — non un prix marché).
DEFAULT_RISK_FREE_RATE: float = 0.04
#: Convenience yield annualisé par défaut (non observable : hypothèse neutre de départ).
DEFAULT_CONVENIENCE_YIELD: float = 0.0


def carry_forward(
    spot: float,
    rate: float,
    convenience_yield: float,
    tau_years: float,
) -> float:
    """Prix forward cost-of-carry ``F = S·e^{(r−y)τ}``.

    Parameters
    ----------
    spot
        Prix spot du compute en $/GPU·h.
    rate
        Taux de financement annualisé ``r``.
    convenience_yield
        Convenience yield annualisé ``y`` (bénéfice de détention du sous-jacent).
    tau_years
        Maturité ``τ`` en années (``τ = 0`` ⇒ ``F = S``).

    Returns
    -------
    float
        Prix forward théorique en $/GPU·h.
    """
    return spot * math.exp((rate - convenience_yield) * tau_years)


def implied_convenience_yield(
    spot: float,
    forward: float,
    rate: float,
    tau_years: float,
) -> float:
    """Convenience yield implicite ``y = r − ln(F/S)/τ`` — inverse de :func:`carry_forward`.

    Permet d'extraire l'hypothèse ``y`` contenue dans une forward donnée (p. ex. la
    courbe Schwartz simulée de P04), le yield n'étant pas observable directement.

    Raises
    ------
    ValueError
        Si ``tau_years <= 0`` (inversion indéfinie) ou si ``spot``/``forward`` <= 0.
    """
    if tau_years <= 0:
        raise ValueError("tau_years doit être > 0 pour inverser le carry.")
    if spot <= 0 or forward <= 0:
        raise ValueError("spot et forward doivent être > 0 (logarithme défini).")
    return rate - math.log(forward / spot) / tau_years


@dataclass(frozen=True)
class CarrySensitivities:
    """Sensibilités analytiques (dérivées premières) du forward cost-of-carry."""

    d_forward_d_rate: float  # ∂F/∂r = F·τ
    d_forward_d_yield: float  # ∂F/∂y = −F·τ
    d_forward_d_tau: float  # ∂F/∂τ = F·(r−y)


def carry_sensitivities(
    spot: float,
    rate: float,
    convenience_yield: float,
    tau_years: float,
) -> CarrySensitivities:
    """Dérivées premières de ``F`` : ``∂F/∂r = F·τ``, ``∂F/∂y = −F·τ``, ``∂F/∂τ = F·(r−y)``."""
    forward = carry_forward(spot, rate, convenience_yield, tau_years)
    return CarrySensitivities(
        d_forward_d_rate=forward * tau_years,
        d_forward_d_yield=-forward * tau_years,
        d_forward_d_tau=forward * (rate - convenience_yield),
    )


@dataclass(frozen=True)
class CostOfCarryModel:
    """Modèle de portage analytique — implémente le protocole ``CarryModel``.

    Le forward produit est **toujours** ``simulated=True`` : les futures compute
    (settlement SDH100RT) ne sont pas listés, tout prix est théorique.
    """

    rate: float = DEFAULT_RISK_FREE_RATE
    convenience_yield: float = DEFAULT_CONVENIENCE_YIELD

    @property
    def name(self) -> str:
        return "cost_of_carry"

    @property
    def simulated(self) -> bool:
        return True

    def forward(self, spot: float, tau_years: float) -> float:
        """Prix forward cost-of-carry pour ce ``(rate, convenience_yield)``."""
        return carry_forward(spot, self.rate, self.convenience_yield, tau_years)
