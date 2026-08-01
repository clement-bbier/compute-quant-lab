"""Theoretical compute derivatives (unlisted futures) -- P06 Strategy layer.

Warning, real versus simulated boundary: the CME compute futures (settling on the
Silicon Data SDH100RT index) are **announced but not listed** (regulatory review).
Every price produced here is therefore **theoretical/simulated** -- :class:`FuturesQuote`
carries a mandatory ``simulated`` field (no default value), enforced by the type and
covered by tests.

Standalone subpackage of :mod:`core.pricing`: it does not alter the P01 API (spark
spread). Re-exporting these symbols from ``core/pricing/__init__.py`` remains an
open gap: importing via ``core.pricing.derivatives`` directly works today.
"""

from __future__ import annotations

from core.pricing.derivatives.carry import (
    DEFAULT_CONVENIENCE_YIELD,
    DEFAULT_RISK_FREE_RATE,
    CarrySensitivities,
    CostOfCarryModel,
    carry_forward,
    carry_sensitivities,
    implied_convenience_yield,
)
from core.pricing.derivatives.futures import CarryFuturesPricer, FuturesQuote
from core.pricing.derivatives.protocols import CarryModel, FuturesPricer

__all__ = [
    # Contracts (DI / SOLID).
    "CarryModel",
    "FuturesPricer",
    # Cost-of-carry core (pure functions).
    "carry_forward",
    "implied_convenience_yield",
    "carry_sensitivities",
    "CarrySensitivities",
    "CostOfCarryModel",
    "DEFAULT_RISK_FREE_RATE",
    "DEFAULT_CONVENIENCE_YIELD",
    # Orchestrator plus result.
    "CarryFuturesPricer",
    "FuturesQuote",
]
