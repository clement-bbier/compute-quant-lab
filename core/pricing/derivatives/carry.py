"""Cost-of-carry core of compute futures pricing (theoretical / SIMULATED).

Carry model: ``F = S·e^{(r−y)τ}`` where ``r`` is the annualised funding rate, ``y``
the annualised convenience yield (not observable, hence assumed or *inferred* from a
forward) and ``τ`` the maturity in years. Convergence property: ``F(τ=0) = S``.
Contango if ``r > y``, backwardation if ``y > r``.

Pure functions (python-quality rule): no I/O, no dependency on ``projects/``.
Units: ``spot``/``forward`` in $/GPU·h; ``rate``/``convenience_yield`` annualised.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

#: Default annualised funding rate (documented PoC assumption -- not a market price).
DEFAULT_RISK_FREE_RATE: float = 0.04
#: Default annualised convenience yield (not observable: neutral starting assumption).
DEFAULT_CONVENIENCE_YIELD: float = 0.0


def carry_forward(
    spot: float,
    rate: float,
    convenience_yield: float,
    tau_years: float,
) -> float:
    """Cost-of-carry forward price ``F = S·e^{(r−y)τ}``.

    Parameters
    ----------
    spot
        Spot price of compute in $/GPU·h.
    rate
        Annualised funding rate ``r``.
    convenience_yield
        Annualised convenience yield ``y`` (benefit of holding the underlying).
    tau_years
        Maturity ``τ`` in years (``τ = 0`` implies ``F = S``).

    Returns
    -------
    float
        Theoretical forward price in $/GPU·h.
    """
    return spot * math.exp((rate - convenience_yield) * tau_years)


def implied_convenience_yield(
    spot: float,
    forward: float,
    rate: float,
    tau_years: float,
) -> float:
    """Implied convenience yield ``y = r − ln(F/S)/τ`` -- inverse of :func:`carry_forward`.

    Extracts the ``y`` assumption embedded in a given forward (for instance the
    simulated Schwartz curve of P04), the yield not being directly observable.

    Raises
    ------
    ValueError
        If ``tau_years <= 0`` (the inversion is undefined) or if ``spot``/``forward``
        are <= 0.
    """
    if tau_years <= 0:
        raise ValueError("tau_years must be > 0 to invert the carry.")
    if spot <= 0 or forward <= 0:
        raise ValueError("spot and forward must be > 0 (the logarithm must be defined).")
    return rate - math.log(forward / spot) / tau_years


@dataclass(frozen=True)
class CarrySensitivities:
    """Analytical sensitivities (first derivatives) of the cost-of-carry forward."""

    d_forward_d_rate: float  # ∂F/∂r = F·τ
    d_forward_d_yield: float  # ∂F/∂y = −F·τ
    d_forward_d_tau: float  # ∂F/∂τ = F·(r−y)


def carry_sensitivities(
    spot: float,
    rate: float,
    convenience_yield: float,
    tau_years: float,
) -> CarrySensitivities:
    """First derivatives of ``F``: ``∂F/∂r = F·τ``, ``∂F/∂y = −F·τ``, ``∂F/∂τ = F·(r−y)``."""
    forward = carry_forward(spot, rate, convenience_yield, tau_years)
    return CarrySensitivities(
        d_forward_d_rate=forward * tau_years,
        d_forward_d_yield=-forward * tau_years,
        d_forward_d_tau=forward * (rate - convenience_yield),
    )


@dataclass(frozen=True)
class CostOfCarryModel:
    """Analytical carry model -- implements the ``CarryModel`` protocol.

    The forward it produces is **always** ``simulated=True``: compute futures
    (SDH100RT settlement) are not listed, so every price is theoretical.
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
        """Cost-of-carry forward price for this ``(rate, convenience_yield)`` pair."""
        return carry_forward(spot, self.rate, self.convenience_yield, tau_years)
