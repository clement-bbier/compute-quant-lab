"""Contracts (abstractions) of the digital spark spread pricer.

`SparkSpreadPricer` depends on these `Protocol` classes, never on concrete
implementations (Dependency Inversion Principle). Every interchangeable price source,
power model, FX converter or computation kernel conforms to one of these contracts --
which makes the pricer testable with mocks and allows the Rust kernel to be
substituted for the Python oracle through plain injection.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import pandas as pd

#: Re-exported from :mod:`core.utils.types` so the public alias name is unchanged.
from core.utils.types import FloatArray


@runtime_checkable
class PriceSource(Protocol):
    """Provides both price legs, UTC-indexed, point-in-time.

    The returned series are already aligned on what was *known at t*: a value at
    instant ``t`` uses no information published after ``t`` (the source applies any
    publication lag itself).
    """

    def energy_price(self, region: str) -> pd.Series:
        """Spot electricity price in €/MWh (tz-aware UTC index)."""
        ...

    def compute_price(self, gpu: str) -> pd.Series:
        """Compute rental price in $/GPU·h (tz-aware UTC index)."""
        ...


@runtime_checkable
class PowerModel(Protocol):
    """Energy model of a GPU: IT power and datacenter efficiency."""

    def power_kw_per_gpu(self) -> float:
        """Average IT power per GPU in kW (TDP, excluding cooling)."""
        ...

    def pue(self) -> float:
        """Power Usage Effectiveness (total draw / IT draw), dimensionless."""
        ...


@runtime_checkable
class FxConverter(Protocol):
    """Point-in-time USD/EUR conversion."""

    def to_eur(self, amount_usd: pd.Series) -> pd.Series:
        """Convert a USD series to EUR at the rate known at each timestamp.

        The result is aligned on ``amount_usd.index``; every amount is converted
        with the FX rate *known at* its own timestamp (anti look-ahead).
        """
        ...


@runtime_checkable
class SpreadKernel(Protocol):
    """Interchangeable vectorised spread computation kernel (Python or Rust).

    Every implementation produces a strictly identical result on the same inputs
    (the Python oracle is the reference for Rust parity).
    """

    def compute(
        self,
        compute_eur_per_gpu_h: FloatArray,
        energy_eur_per_mwh: FloatArray,
        power_kw_per_gpu: FloatArray,
        pue: FloatArray,
    ) -> tuple[FloatArray, FloatArray, FloatArray]:
        """Compute ``(revenue, cost, spread)`` element-wise.

        Parameters
        ----------
        compute_eur_per_gpu_h
            Compute revenue in €/GPU·h (already converted from USD).
        energy_eur_per_mwh
            Electricity price in €/MWh.
        power_kw_per_gpu
            IT power per GPU in kW.
        pue
            Power Usage Effectiveness.

        Returns
        -------
        tuple of FloatArray
            ``revenue`` (= compute), ``cost`` (energy), ``spread`` (= revenue − cost),
            each of the same length as the inputs.
        """
        ...
