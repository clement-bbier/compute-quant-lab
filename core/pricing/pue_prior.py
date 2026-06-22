"""Prior PUE region-keyed (truncated-normal), conforme à la fiche L0 §8.

Prior **strict** : jamais mis à jour par les prix observés (interdit de fit-to-price,
cf. revue risk-validator). Fournit un *point estimate* (μ, chemin de pricing central)
et des *bornes de sensibilité* (le support), propagées en bandes par le pricer.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.stats import truncnorm


@dataclass(frozen=True)
class PuePrior:
    """Distribution truncated-normal sur le PUE (≥ 1 par construction via ``low``).

    Parameters
    ----------
    mu
        Moyenne du prior (PUE central, point estimate du pricing).
    sigma
        Écart-type avant troncature.
    low, high
        Support [low, high]. ``low`` ≥ 1.0 (le datacenter consomme ≥ l'IT).
    """

    mu: float
    sigma: float
    low: float
    high: float

    def __post_init__(self) -> None:
        if self.sigma <= 0:
            raise ValueError("sigma doit être strictement positif")
        if self.low < 1.0:
            raise ValueError("PUE >= 1.0 : `low` ne peut être < 1.0")
        if not (self.low <= self.mu <= self.high):
            raise ValueError("mu doit être dans le support [low, high]")

    def _dist(self) -> truncnorm:
        a = (self.low - self.mu) / self.sigma
        b = (self.high - self.mu) / self.sigma
        return truncnorm(a, b, loc=self.mu, scale=self.sigma)

    def point_estimate(self) -> float:
        """μ — le PUE central utilisé pour le spread de référence."""
        return self.mu

    def sensitivity_bounds(self) -> tuple[float, float]:
        """Support [low, high] — bornes des bandes de sensibilité du pricing."""
        return (self.low, self.high)

    def sample(self, n: int, *, seed: int) -> NDArray[np.float64]:
        """Tirage reproductible de ``n`` PUE (déterminisme exigé par le labo)."""
        rng = np.random.default_rng(seed)
        return self._dist().rvs(size=n, random_state=rng).astype(np.float64)


# Conforme L0 §8 (Texas centré plus haut pour le refroidissement).
ERCOT_TEXAS_PRIOR = PuePrior(mu=1.45, sigma=0.15, low=1.2, high=1.8)
