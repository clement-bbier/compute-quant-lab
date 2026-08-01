"""Region-keyed PUE prior (truncated normal), following note L0 section 8.

**Strict** prior: never updated from observed prices (fit-to-price is forbidden, see
the risk-validator review). Provides a *point estimate* (mu, the central pricing path)
and *sensitivity bounds* (the support), propagated as bands by the pricer.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.stats import truncnorm


@dataclass(frozen=True)
class PuePrior:
    """Truncated-normal distribution over the PUE (>= 1 by construction via ``low``).

    Parameters
    ----------
    mu
        Mean of the prior (central PUE, point estimate used for pricing).
    sigma
        Standard deviation before truncation.
    low, high
        Support [low, high]. ``low`` >= 1.0 (the datacenter draws at least the IT load).
    """

    mu: float
    sigma: float
    low: float
    high: float

    def __post_init__(self) -> None:
        if self.sigma <= 0:
            raise ValueError("sigma must be strictly positive.")
        if self.low < 1.0:
            raise ValueError("low must be >= 1.0 (PUE cannot be below 1.0).")
        if not (self.low <= self.mu <= self.high):
            raise ValueError("mu must lie within the support [low, high].")

    def _dist(self) -> truncnorm:
        a = (self.low - self.mu) / self.sigma
        b = (self.high - self.mu) / self.sigma
        return truncnorm(a, b, loc=self.mu, scale=self.sigma)

    def point_estimate(self) -> float:
        """mu -- the central PUE used for the reference spread."""
        return self.mu

    def sensitivity_bounds(self) -> tuple[float, float]:
        """Support [low, high] -- bounds of the pricing sensitivity bands."""
        return (self.low, self.high)

    def sample(self, n: int, *, seed: int) -> NDArray[np.float64]:
        """Reproducible draw of ``n`` PUE values (determinism required by the lab)."""
        rng = np.random.default_rng(seed)
        return self._dist().rvs(size=n, random_state=rng).astype(np.float64)


# Follows L0 section 8 (Texas centred higher because of cooling).
ERCOT_TEXAS_PRIOR = PuePrior(mu=1.45, sigma=0.15, low=1.2, high=1.8)
