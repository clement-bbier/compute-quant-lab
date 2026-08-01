"""Monte-Carlo forward engine backed by the Rust ``forward_engine`` crate.

Implements :class:`~forward.protocols.ForwardCurveModel` by delegating the simulation
(many paths) to Rust code for performance, while remaining interchangeable
with the Python oracle (same interface). The crate is installed via
``maturin develop -m projects/04_compute_index_curve/forward_engine/Cargo.toml``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from forward.models import Curve, CurvePoint, SchwartzParams


@dataclass(frozen=True)
class RustMonteCarloForward:
    """Forward curve via Rust Monte-Carlo (1-factor Schwartz, exact OU transition)."""

    n_paths: int = 100_000
    seed: int = 0

    @property
    def name(self) -> str:
        return "schwartz_mc_rust"

    def simulate(
        self,
        spot: float,
        params: SchwartzParams,
        maturities_days: Sequence[float],
    ) -> Curve:
        import forward_engine  # deferred import: the crate may not be built

        maturities = [float(m) for m in maturities_days]
        prices = forward_engine.simulate_forward(
            spot,
            params.kappa,
            params.theta,
            params.sigma,
            maturities,
            self.n_paths,
            self.seed,
        )
        points = tuple(CurvePoint(m, p) for m, p in zip(maturities, prices))
        return Curve(
            spot=spot,
            points=points,
            model_name=self.name,
            simulated=True,
            params=params,
            seed=self.seed,
            n_paths=self.n_paths,
        )
