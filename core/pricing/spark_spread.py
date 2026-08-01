"""Digital spark spread: translates electricity into a cost of compute, then compares
that marginal cost with the market price of compute to derive a margin.

Reference figures (see the lab thesis):
    A server of 8x Nvidia H100 draws ~10.2 kW (cooling included, through the PUE).
    At 150 €/MWh, energy costs ~1.53 €/h for the server, i.e. ~0.19 €/h per GPU.
"""

from __future__ import annotations

from dataclasses import dataclass

# --- Default physical constants (overridable, never hard-coded elsewhere) ---
DEFAULT_GPUS_PER_SERVER: int = 8
DEFAULT_SERVER_POWER_KW: float = 10.2  # kW for 8x H100, PUE included
MWH_TO_KWH: float = 1000.0


@dataclass(frozen=True)
class ServerSpec:
    """Energy characteristics of a GPU server."""

    n_gpus: int = DEFAULT_GPUS_PER_SERVER
    total_power_kw: float = DEFAULT_SERVER_POWER_KW

    @property
    def power_kw_per_gpu(self) -> float:
        """Average power drawn per GPU (kW), cooling included."""
        return self.total_power_kw / self.n_gpus


def energy_cost_per_gpu_hour(
    electricity_price_eur_per_mwh: float,
    spec: ServerSpec | None = None,
) -> float:
    """Marginal energy cost of one GPU-hour, in euros.

    Parameters
    ----------
    electricity_price_eur_per_mwh
        Spot electricity price (€/MWh), for instance coming from ENTSO-E.
    spec
        Server specification. Default: 8x H100 at 10.2 kW (PUE included).

    Returns
    -------
    float
        Energy cost in €/h/GPU. At 150 €/MWh: ~0.19 €/h/GPU.
    """
    spec = spec or ServerSpec()
    price_eur_per_kwh = electricity_price_eur_per_mwh / MWH_TO_KWH
    return spec.power_kw_per_gpu * price_eur_per_kwh


def spark_spread_per_gpu_hour(
    compute_price_eur_per_gpu_hour: float,
    electricity_price_eur_per_mwh: float,
    spec: ServerSpec | None = None,
) -> float:
    """Gross margin of one GPU-hour: market price of compute − energy cost.

    A positive spread means producing compute is profitable at the current energy
    price. This is the base signal of the energy versus compute arbitrage.
    """
    cost = energy_cost_per_gpu_hour(electricity_price_eur_per_mwh, spec)
    return compute_price_eur_per_gpu_hour - cost
