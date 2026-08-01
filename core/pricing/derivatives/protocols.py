"""Contracts (abstractions) of theoretical compute futures pricing.

:class:`~core.pricing.derivatives.futures.CarryFuturesPricer` depends on these
``Protocol`` classes, never on a concrete implementation (Dependency Inversion
Principle). Any forward source -- an analytical carry model
(:class:`CostOfCarryModel`) or an adapter of the **simulated** Schwartz curve of
P04 -- conforms to ``CarryModel``, which makes the pricer testable with mocks and
the forward injectable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from core.pricing.derivatives.futures import FuturesQuote


@runtime_checkable
class CarryModel(Protocol):
    """Strategy producing a theoretical forward price from the spot.

    Real versus simulated boundary: ``simulated`` is part of the contract. Since
    compute futures are not listed, every forward produced here is simulated.
    """

    @property
    def name(self) -> str:
        """Model identifier (recorded in MLflow)."""
        ...

    @property
    def simulated(self) -> bool:
        """``True`` if the forward is simulated/theoretical (never a market price)."""
        ...

    def forward(self, spot: float, tau_years: float) -> float:
        """Forward price in $/GPU·h for a ``tau_years`` maturity (in years)."""
        ...


@runtime_checkable
class FuturesPricer(Protocol):
    """Orchestrator: prices a theoretical compute future into a ``FuturesQuote``."""

    def price(self, spot: float, tau_years: float) -> FuturesQuote:
        """Quote the future from the spot and the maturity (simulated quote)."""
        ...
