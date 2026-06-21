"""Types immuables de la courbe forward compute (SIMULÉE).

⚠️ Frontière réel/simulé : un :class:`Curve` porte un champ ``simulated`` **obligatoire**
(sans valeur par défaut). Impossible de construire une courbe sans déclarer si elle est
réelle ou simulée — la garantie est portée par le type, pas par une convention. Les
futures compute CME (settlement sur l'indice Silicon Data SDH100RT) ne sont pas listés :
toute courbe produite ici est ``simulated=True``.

Unités : prix en $/GPU·h, échéances ``maturity_days`` en jours, ``kappa`` par jour.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class SchwartzParams:
    """Paramètres du modèle de Schwartz un-facteur (OU sur le log-prix).

    ``d ln S = kappa (ln theta - ln S) dt + sigma dW`` : mean-reversion adaptée aux
    commodités non stockables (analogie électricité).
    """

    kappa: float  # vitesse de retour à la moyenne (par jour), > 0
    theta: float  # niveau de long terme ($/GPU·h), > 0
    sigma: float  # volatilité instantanée, >= 0

    def __post_init__(self) -> None:
        if self.kappa <= 0:
            raise ValueError("kappa doit être > 0 (vitesse de mean-reversion).")
        if self.theta <= 0:
            raise ValueError("theta doit être > 0 (niveau de long terme).")
        if self.sigma < 0:
            raise ValueError("sigma doit être >= 0 (volatilité).")

    @property
    def long_run_forward(self) -> float:
        """Niveau forward asymptotique ``theta * exp(sigma^2 / (4 kappa))`` (τ→∞)."""
        return self.theta * math.exp(self.sigma**2 / (4.0 * self.kappa))


@dataclass(frozen=True)
class CurvePoint:
    """Un point de la courbe : prix forward pour une échéance donnée (jours)."""

    maturity_days: float
    forward_price: float


@dataclass(frozen=True)
class Curve:
    """Courbe forward compute. ``simulated`` est OBLIGATOIRE (frontière réel/simulé).

    ``method``/``model_name``, ``seed`` et ``n_paths`` rendent la courbe rejouable.
    """

    spot: float
    points: tuple[CurvePoint, ...]
    model_name: str
    simulated: bool
    params: SchwartzParams
    seed: int | None = None
    n_paths: int | None = None

    @property
    def maturities(self) -> tuple[float, ...]:
        return tuple(p.maturity_days for p in self.points)

    @property
    def prices(self) -> tuple[float, ...]:
        return tuple(p.forward_price for p in self.points)
