"""Python oracle for the forward curve: analytical + reference Monte-Carlo.

1-factor Schwartz model (OU on the log-price). The **analytical forward** is the
reference (oracle) against which the Rust engine is tested; the **Python MC** reproduces
the same exact transition scheme, useful as a fallback and as a cross-check.

Forward (expectation of spot under the model, lognormal price):

    F(t, T) = exp( e^{-kτ} ln S_t + (1 - e^{-kτ}) ln θ + ½ · (σ²/2k)(1 - e^{-2kτ}) )

Properties: F(τ=0) = S_t (convergence); monotone from S_t toward the long-run level.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

import numpy as np

from forward.models import Curve, CurvePoint, SchwartzParams


def forward_price(spot: float, params: SchwartzParams, tau_days: float) -> float:
    """Analytical forward price for a ``tau_days`` maturity (days)."""
    if tau_days == 0:
        return spot
    k, theta, sigma = params.kappa, params.theta, params.sigma
    decay = math.exp(-k * tau_days)
    mean_log = decay * math.log(spot) + (1.0 - decay) * math.log(theta)
    var_log = (sigma**2 / (2.0 * k)) * (1.0 - math.exp(-2.0 * k * tau_days))
    return math.exp(mean_log + 0.5 * var_log)


@dataclass(frozen=True)
class SchwartzAnalyticForward:
    """Closed-form forward curve (reference oracle for parity checks)."""

    @property
    def name(self) -> str:
        return "schwartz_analytic"

    def simulate(
        self,
        spot: float,
        params: SchwartzParams,
        maturities_days: Sequence[float],
    ) -> Curve:
        points = tuple(
            CurvePoint(float(tau), forward_price(spot, params, float(tau)))
            for tau in maturities_days
        )
        return Curve(
            spot=spot,
            points=points,
            model_name=self.name,
            simulated=True,
            params=params,
        )


@dataclass(frozen=True)
class PythonMonteCarloForward:
    """Python Monte-Carlo (exact OU transition) — fallback and cross-check.

    Samples ``n_paths`` paths, stepping forward via exact transitions between
    consecutive maturities: unbiased estimator of the analytical forward.
    """

    n_paths: int = 100_000
    seed: int | None = None

    @property
    def name(self) -> str:
        return "schwartz_mc_python"

    def simulate(
        self,
        spot: float,
        params: SchwartzParams,
        maturities_days: Sequence[float],
    ) -> Curve:
        rng = np.random.default_rng(self.seed)
        k, theta, sigma = params.kappa, params.theta, params.sigma
        ln_theta = math.log(theta)

        maturities = [float(m) for m in maturities_days]
        x = np.full(self.n_paths, math.log(spot))
        forwards: dict[float, float] = {}
        previous = 0.0
        for maturity in sorted(set(maturities)):
            step = maturity - previous
            if step > 0:
                decay = math.exp(-k * step)
                var = (sigma**2 / (2.0 * k)) * (1.0 - math.exp(-2.0 * k * step))
                x = (
                    decay * x
                    + (1.0 - decay) * ln_theta
                    + math.sqrt(var) * rng.standard_normal(self.n_paths)
                )
            forwards[maturity] = float(np.mean(np.exp(x)))
            previous = maturity

        points = tuple(CurvePoint(m, forwards[m]) for m in maturities)
        return Curve(
            spot=spot,
            points=points,
            model_name=self.name,
            simulated=True,
            params=params,
            seed=self.seed,
            n_paths=self.n_paths,
        )
