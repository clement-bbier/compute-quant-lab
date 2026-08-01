"""Quote and orchestrator of compute futures pricing (theoretical / SIMULATED).

:class:`FuturesQuote` carries a **mandatory** ``simulated`` field (no default value):
the real versus simulated boundary is enforced by the type, not by convention.
:class:`CarryFuturesPricer` injects a forward (through ``CarryModel``) and *always*
infers the implied convenience yield -- which unifies exogenous carry pricing and the
use of the simulated Schwartz curve of P04 under a single logic.
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
    """Theoretical quote of a compute future for a given maturity.

    ``simulated`` is **mandatory** (no default): compute futures (SDH100RT settlement)
    are not listed, so no quote can "forget" that it is theoretical. Units: prices in
    $/GPU·h, ``maturity_years`` in years, rates annualised.
    """

    spot: float
    forward: float
    maturity_years: float
    basis: float  # F − S, the spot/forward basis
    rate: float
    convenience_yield: float  # implied, inferred from the forward
    model_name: str
    sensitivities: CarrySensitivities
    simulated: bool


class CarryFuturesPricer:
    """Price a theoretical compute future from an injected forward.

    Parameters
    ----------
    model : CarryModel
        Forward source (analytical carry model or an adapter of the P04 forward).
    rate : float
        Annualised funding rate ``r`` used to invert the forward (implied convenience
        yield) and to compute the sensitivities.

    Because the yield is inferred from the supplied forward, the pricer returns the
    exogenous ``y`` back for a :class:`CostOfCarryModel` (round-trip) and *extracts*
    the implied ``y`` from a simulated Schwartz forward.
    """

    def __init__(self, model: CarryModel, rate: float = DEFAULT_RISK_FREE_RATE) -> None:
        self._model = model
        self._rate = rate

    def price(self, spot: float, tau_years: float) -> FuturesQuote:
        """Quote the future: forward, then basis, implied yield and sensitivities."""
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
