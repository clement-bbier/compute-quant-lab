"""Moteur forward Monte-Carlo adossé à la crate Rust ``forward_engine``.

Implémente :class:`~forward.protocols.ForwardCurveModel` en déléguant la simulation
(nombreux chemins) au code Rust pour la performance, tout en restant interchangeable
avec l'oracle Python (même interface). La crate s'installe via
``maturin develop -m projects/04_compute_index_curve/forward_engine/Cargo.toml``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from forward.models import Curve, CurvePoint, SchwartzParams


@dataclass(frozen=True)
class RustMonteCarloForward:
    """Courbe forward par Monte-Carlo Rust (Schwartz un-facteur, transition OU exacte)."""

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
        import forward_engine  # import différé : la crate peut ne pas être buildée

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
