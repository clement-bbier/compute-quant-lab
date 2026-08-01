"""Reference vectorised spread kernel (pure numpy).

This is the *canonical* implementation of `SpreadKernel`: the oracle against which
the parity of the Rust kernel is tested. Pure, no I/O, no state -- substitutable by
the Rust kernel through plain injection into the pricer.
"""

from __future__ import annotations

from core.pricing.protocols import FloatArray

KWH_PER_MWH: float = 1000.0


class PythonOracle:
    """Reference Python kernel (implements `SpreadKernel`)."""

    def compute(
        self,
        compute_eur_per_gpu_h: FloatArray,
        energy_eur_per_mwh: FloatArray,
        power_kw_per_gpu: FloatArray,
        pue: FloatArray,
    ) -> tuple[FloatArray, FloatArray, FloatArray]:
        """Compute ``(revenue, cost, spread)`` element-wise.

        The energy cost of one GPU-hour is ``power_kw · pue · (EUR/MWh) / 1000``:
        the IT power (kW), scaled up by the PUE to account for cooling, drawn for
        one hour (kWh), at the electricity price expressed in EUR/kWh.
        """
        revenue = compute_eur_per_gpu_h
        cost = power_kw_per_gpu * pue * energy_eur_per_mwh / KWH_PER_MWH
        spread = revenue - cost
        return revenue, cost, spread
