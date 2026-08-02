"""Vectorised digital spark spread pricer (DI/SOLID orchestration).

`SparkSpreadPricer` depends on abstractions (`PriceSource`, `PowerModel`,
`FxConverter`, `SpreadKernel`), never on concrete implementations (DIP). It stays a
**pure function**: no hidden I/O, every side effect (network, disk) lives in
`projects/01_.../src/`.

Kernel selection happens by injection: Rust if provided, otherwise the Python oracle.
The Rust subcrate (source at `core/pricing/_kernel/`, installs as the top-level
`_kernel` extension) is optional; its absence only degrades performance, never
the result.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from core.pricing.efficiency import tflops_fp16
from core.pricing.oracle import PythonOracle
from core.pricing.power_model import ServerPowerModel
from core.pricing.protocols import (
    FloatArray,
    FxConverter,
    PowerModel,
    PriceSource,
    SpreadKernel,
)
from core.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class SpreadResult:
    """Pricing result: revenue/cost decomposition plus metadata.

    The explicit decomposition (`revenue`, `cost`, `spread`) answers the requirement
    of prompt P01 section 3a; the metadata records the assumptions of the computation.
    """

    spread: pd.Series
    revenue: pd.Series
    cost: pd.Series
    gpu: str
    region: str
    pue: float
    power_kw_per_gpu: float
    fx: str
    window: tuple[pd.Timestamp, pd.Timestamp]


class RustKernel:
    """Adapter from the optional Rust subcrate to the `SpreadKernel` protocol.

    Only instantiable if the ``_kernel`` extension has been compiled (``maturin
    develop -m core/pricing/_kernel/Cargo.toml``); raises `ImportError` otherwise.
    """

    def __init__(self) -> None:
        import importlib  # noqa: PLC0415 (optional runtime import)

        # Top-level import, NOT "core.pricing._kernel": the pyo3 crate's [lib] name
        # is "_kernel" (flat), so maturin installs it at site-packages/_kernel/.
        # Importing it as a submodule of core.pricing would instead resolve to the
        # on-disk core/pricing/_kernel/ source directory (an implicit namespace
        # package with no `compute` attribute), making this silently un-instantiable
        # even when the crate is compiled.
        kernel = importlib.import_module("_kernel")
        self._compute = kernel.compute

    def compute(
        self,
        compute_eur_per_gpu_h: FloatArray,
        energy_eur_per_mwh: FloatArray,
        power_kw_per_gpu: FloatArray,
        pue: FloatArray,
    ) -> tuple[FloatArray, FloatArray, FloatArray]:
        return self._compute(  # type: ignore[no-any-return]
            np.ascontiguousarray(compute_eur_per_gpu_h, dtype=np.float64),
            np.ascontiguousarray(energy_eur_per_mwh, dtype=np.float64),
            np.ascontiguousarray(power_kw_per_gpu, dtype=np.float64),
            np.ascontiguousarray(pue, dtype=np.float64),
        )


def _default_kernel() -> SpreadKernel:
    """Rust fast path if compiled, else the Python oracle (bit-for-bit identical results).

    Mirrors ``core.backtest.engine``'s kernel-selection logging: the Rust/Python choice
    is a fallback (per the module docstring, absence of the crate only degrades
    performance) and must therefore be visible, not silently decided once per pricer.
    """
    try:
        return RustKernel()
    except ImportError:
        logger.warning(
            "Rust kernel '_kernel' unavailable: falling back to the Python oracle (slow path, "
            "bit-for-bit identical results). Run 'maturin develop -m "
            "core/pricing/_kernel/Cargo.toml' for the fast path."
        )
        return PythonOracle()


class SparkSpreadPricer:
    """Price the digital spark spread over a time grid, point-in-time.

    Parameters
    ----------
    power_model
        Power/PUE model (the `PowerModel` abstraction).
    fx
        USD/EUR converter (the `FxConverter` abstraction).
    kernel
        Computation kernel (the `SpreadKernel` abstraction). Default: Python oracle.
    """

    def __init__(
        self,
        power_model: PowerModel,
        fx: FxConverter,
        kernel: SpreadKernel | None = None,
    ) -> None:
        self._power_model = power_model
        self._fx = fx
        self._kernel: SpreadKernel = kernel if kernel is not None else _default_kernel()

    def price(self, source: PriceSource, gpu: str, region: str) -> SpreadResult:
        """Compute the spread in EUR/GPU·h on the grid of the energy leg.

        Energy (with its deep history) carries the evaluation grid; compute is aligned
        onto it by a **backward** as-of join (last price known at each instant) -- no
        future price enters the spread at ``t``.
        """
        return self._price_at_pue(source, gpu, region, self._power_model.pue())

    def _price_at_pue(self, source: PriceSource, gpu: str, region: str, pue: float) -> SpreadResult:
        """Central pricing path, parameterised by the PUE (reused by the bands)."""
        energy = source.energy_price(region)
        compute_usd = source.compute_price(gpu)
        compute_eur = self._fx.to_eur(compute_usd).sort_index()

        grid = energy.sort_index().index
        # ffill = carry forward the last index value <= t: strict backward as-of.
        compute_on_grid = compute_eur.reindex(grid, method="ffill")

        power_kw = self._power_model.power_kw_per_gpu()
        n = len(grid)
        revenue_a, cost_a, spread_a = self._kernel.compute(
            compute_on_grid.to_numpy(dtype=np.float64),
            energy.reindex(grid).to_numpy(dtype=np.float64),
            np.full(n, power_kw, dtype=np.float64),
            np.full(n, pue, dtype=np.float64),
        )

        return SpreadResult(
            spread=pd.Series(spread_a, index=grid, name="spread"),
            revenue=pd.Series(revenue_a, index=grid, name="revenue"),
            cost=pd.Series(cost_a, index=grid, name="cost"),
            gpu=gpu,
            region=region,
            pue=pue,
            power_kw_per_gpu=power_kw,
            fx=repr(self._fx),
            window=(grid[0], grid[-1]),
        )

    def normalized_spread(self, res: SpreadResult) -> pd.Series:
        """Spread brought back to the unit of account: EUR/GPU·h **per TFLOP** (dense FP16).

        Makes the spread comparable across GPUs of differing efficiency.
        """
        return (res.spread / tflops_fp16(res.gpu)).rename("normalized_spread")

    def pue_sensitivity(
        self, source: PriceSource, gpu: str, region: str
    ) -> tuple[SpreadResult, SpreadResult]:
        """Re-price at the bounds of the PUE prior, yielding a ``(low_pue, high_pue)`` band.

        Requires a `ServerPowerModel` built with a `PuePrior`. The central `price()`
        path is left untouched (parity preserved).
        """
        pm = self._power_model
        bounds = pm.pue_bounds() if isinstance(pm, ServerPowerModel) else None
        if bounds is None:
            raise ValueError(
                "power_model must be a ServerPowerModel built with a PuePrior for pue_sensitivity."
            )
        low, high = bounds
        return (
            self._price_at_pue(source, gpu, region, low),
            self._price_at_pue(source, gpu, region, high),
        )
