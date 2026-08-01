"""Energy model of a GPU server.

Cleanly separates the *IT* power (GPU TDP) from datacenter efficiency (PUE), where
the historical scalar building block (`spark_spread.py`) handled only a
"PUE-included" power figure. This separation makes the PUE lever explicit, as
required by the sensitivity study of prompt P01.
"""

from __future__ import annotations

from core.pricing.pue_prior import PuePrior

WATTS_PER_KILOWATT: float = 1000.0


class ServerPowerModel:
    """Power model of a multi-GPU server (implements `PowerModel`).

    Calibrated by default on the lab thesis: 8x H100 at 700 W TDP and PUE 1.82
    reproduce the ~10.2 kW per server (and ~0.19 EUR/h/GPU at 150 EUR/MWh) of the
    reference building block.

    Parameters
    ----------
    tdp_w
        IT power (TDP) of one GPU, in watts.
    pue
        Power Usage Effectiveness of the datacenter (dimensionless, >= 1). Accepts a
        ``float`` scalar or a ``PuePrior`` (region-keyed): in the latter case the
        central pricing path uses the *point estimate* and exposes the bounds through
        ``pue_bounds()``.
    n_gpus
        Number of GPUs in the server (metadata, for server-level aggregation).
    """

    def __init__(self, tdp_w: float, pue: float | PuePrior, n_gpus: int) -> None:
        if tdp_w <= 0:
            raise ValueError("tdp_w must be strictly positive.")
        if n_gpus <= 0:
            raise ValueError("n_gpus must be strictly positive.")
        if isinstance(pue, PuePrior):
            self._pue_value = pue.point_estimate()
            self._pue_prior: PuePrior | None = pue
        else:
            if pue < 1.0:
                raise ValueError("pue must be >= 1.0 (the datacenter draws at least the IT load).")
            self._pue_value = pue
            self._pue_prior = None
        self._tdp_w = tdp_w
        self._n_gpus = n_gpus

    def power_kw_per_gpu(self) -> float:
        """IT power per GPU in kW (excluding cooling, which the PUE adds)."""
        return self._tdp_w / WATTS_PER_KILOWATT

    def pue(self) -> float:
        """Power Usage Effectiveness of the datacenter (point estimate if a prior)."""
        return self._pue_value

    def pue_bounds(self) -> tuple[float, float] | None:
        """Sensitivity bounds [low, high] if a `PuePrior` was given, else None."""
        return self._pue_prior.sensitivity_bounds() if self._pue_prior else None

    @property
    def n_gpus(self) -> int:
        """Number of GPUs in the server."""
        return self._n_gpus

    def __repr__(self) -> str:
        return (
            f"ServerPowerModel(tdp_w={self._tdp_w}, pue={self._pue_value}, n_gpus={self._n_gpus})"
        )
