"""Immutable types for the (SIMULATED) compute forward curve.

Warning: real/simulated boundary: a :class:`Curve` carries a **required** ``simulated`` field
(no default value). It is impossible to construct a curve without declaring whether it is
real or simulated — the guarantee is enforced by the type, not by convention. The
CME compute futures (settlement on the Silicon Data SDH100RT index) are not listed:
every curve produced here is ``simulated=True``.

Units: prices in $/GPU·h, maturities ``maturity_days`` in days, ``kappa`` per day.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class SchwartzParams:
    """Parameters of the 1-factor Schwartz model (OU on the log-price).

    ``d ln S = kappa (ln theta - ln S) dt + sigma dW``: mean-reversion suited to
    non-storable commodities (electricity analogy).
    """

    kappa: float  # speed of mean reversion (per day), > 0
    theta: float  # long-run level ($/GPU·h), > 0
    sigma: float  # instantaneous volatility, >= 0

    def __post_init__(self) -> None:
        if self.kappa <= 0:
            raise ValueError("kappa must be > 0 (mean-reversion speed).")
        if self.theta <= 0:
            raise ValueError("theta must be > 0 (long-run level).")
        if self.sigma < 0:
            raise ValueError("sigma must be >= 0 (volatility).")

    @property
    def long_run_forward(self) -> float:
        """Asymptotic forward level ``theta * exp(sigma^2 / (4 kappa))`` (τ→∞)."""
        return self.theta * math.exp(self.sigma**2 / (4.0 * self.kappa))


@dataclass(frozen=True)
class CurvePoint:
    """A single point on the curve: forward price for a given maturity (days)."""

    maturity_days: float
    forward_price: float


@dataclass(frozen=True)
class Curve:
    """Compute forward curve. ``simulated`` is REQUIRED (real/simulated boundary).

    ``method``/``model_name``, ``seed`` and ``n_paths`` make the curve replayable.
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
