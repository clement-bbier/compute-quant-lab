"""Injectable regional config + pricer factory (P05).

A region has its own **PUE**, hardware efficiency (TDP, GPU count) and $/€ exchange
rate. Since PUE lives in P01's ``PowerModel`` (not in the ``price`` call), a regional
PUE requires **one ``SparkSpreadPricer`` per region**: that's the role of
``build_regional_pricer``.

No magic numbers in the logic (rule python-quality): regional constants are named
fields of ``RegionConfig``; ``DEFAULT_REGIONS`` is just a documented set of defaults,
overridable via injection.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.pricing import ConstantFx, ServerPowerModel, SparkSpreadPricer
from core.pricing.protocols import SpreadKernel


@dataclass(frozen=True)
class RegionConfig:
    """Parameters of a region for spark spread pricing.

    Parameters
    ----------
    code
        Region identifier (energy column key, e.g. ``"FR"``, ``"DE"``).
    pue
        Power Usage Effectiveness (dimensionless, ≥ 1.0).
    tdp_w
        IT power draw (TDP) of a GPU, in watts (> 0).
    n_gpus
        Number of GPUs of the reference server (> 0).
    fx_eur_per_usd
        EUR per USD exchange rate applied to compute revenue (> 0).
    label
        Human-readable label (datacenter / zone), traceability only.
    """

    code: str
    pue: float
    tdp_w: float
    n_gpus: int
    fx_eur_per_usd: float
    label: str = ""

    def __post_init__(self) -> None:
        if self.pue < 1.0:
            raise ValueError(f"pue must be ≥ 1.0 (got {self.pue}): total draw ≥ IT draw.")
        if self.tdp_w <= 0:
            raise ValueError(f"tdp_w must be > 0 (got {self.tdp_w}).")
        if self.n_gpus <= 0:
            raise ValueError(f"n_gpus must be > 0 (got {self.n_gpus}).")
        if self.fx_eur_per_usd <= 0:
            raise ValueError(f"fx_eur_per_usd must be > 0 (got {self.fx_eur_per_usd}).")


def build_regional_pricer(
    cfg: RegionConfig, *, kernel: SpreadKernel | None = None
) -> SparkSpreadPricer:
    """Builds a ``SparkSpreadPricer`` (P01) carrying ``cfg``'s PUE/efficiency.

    Pure factory: no I/O. The Rust kernel is injectable (default: Python oracle).
    """
    power_model = ServerPowerModel(tdp_w=cfg.tdp_w, pue=cfg.pue, n_gpus=cfg.n_gpus)
    return SparkSpreadPricer(power_model, ConstantFx(cfg.fx_eur_per_usd), kernel)


# Documented defaults (config, not magic): 8-GPU H100, PUE FR < DE (nuclear vs coal/gas mix),
# EUR/USD FX ~ parity. Overridable via injection in run_basis.py / tests.
DEFAULT_REGIONS: tuple[RegionConfig, ...] = (
    RegionConfig(code="FR", pue=1.20, tdp_w=700.0, n_gpus=8, fx_eur_per_usd=0.92, label="France"),
    RegionConfig(code="DE", pue=1.45, tdp_w=700.0, n_gpus=8, fx_eur_per_usd=0.92, label="Germany"),
)
