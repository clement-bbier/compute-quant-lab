"""Adapter : branche la courbe forward SIMULÉE de P04 dans le contrat ``CarryModel``.

Vit dans la **couche projet** (pas dans ``core/``) afin de ne pas coupler le cœur
``core.pricing.derivatives`` au paquet ``forward`` de ``projects/04`` — ``mypy core``
reste propre et le sens des dépendances est respecté (core ignore les projets).

P04 exprime les maturités en **jours** et ``kappa`` par jour ; le cœur P06 raisonne
en **années** (taux annualisés). L'adapter porte la conversion années → jours.
La forward Schwartz étant un modèle, ``simulated`` est toujours ``True``.
"""

from __future__ import annotations

from dataclasses import dataclass

from forward.models import SchwartzParams
from forward.oracle import forward_price

#: Jours par an pour convertir les maturités (cohérent avec P04, base 365.25).
DAYS_PER_YEAR: float = 365.25


@dataclass(frozen=True)
class P04ForwardAdapter:
    """Expose la forward analytique Schwartz de P04 comme un ``CarryModel``.

    Parameters
    ----------
    params
        Paramètres Schwartz un-facteur (calibrés par P04, ``kappa`` par jour).
    days_per_year
        Facteur de conversion années → jours pour interroger la forward P04.
    """

    params: SchwartzParams
    days_per_year: float = DAYS_PER_YEAR

    @property
    def name(self) -> str:
        return "schwartz_p04"

    @property
    def simulated(self) -> bool:
        return True

    def forward(self, spot: float, tau_years: float) -> float:
        """Prix forward Schwartz P04 pour ``tau_years`` (converti en jours)."""
        return forward_price(spot, self.params, tau_years * self.days_per_year)
