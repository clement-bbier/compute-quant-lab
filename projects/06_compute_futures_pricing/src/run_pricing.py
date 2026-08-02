"""P06 demo: THEORETICAL pricing of compute futures, logged to MLflow.

Reproducible pipeline (known params, deterministic analytic oracle):
  1. loads the **real** compute spot (``core.ingestion``); **logged** fallback to an
     assumption if no snapshot is available (never a silent failure);
  2. builds P04's **SIMULATED** forward curve (analytic Schwartz);
  3. prices the maturity grid via TWO forward sources — exogenous cost-of-carry
     and the P04 adapter — and computes the base ``F − S`` + implied convenience yield;
  4. logs params + metrics to MLflow (``core.utils.tracking.run``);
  5. writes ``results/futures_pricing_summary.json`` with the real/simulated disclaimer.

WARNING: all prices are THEORETICAL/SIMULATED: compute futures (SDH100RT settlement)
are not listed. Never present these figures as an observed market.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
from pathlib import Path
from typing import Any

# MLflow >= 3 puts the file store into "maintenance mode": explicit opt-out (before import).
os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")

import mlflow  # noqa: E402 - after the file-store opt-out above

REPO_ROOT = Path(__file__).resolve().parents[3]
_P06_SRC = Path(__file__).resolve().parent
_P04_SRC = REPO_ROOT / "projects" / "04_compute_index_curve" / "src"
for _path in (str(_P06_SRC), str(_P04_SRC)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from core.pricing.derivatives import (  # noqa: E402
    DEFAULT_RISK_FREE_RATE,
    CarryFuturesPricer,
    CostOfCarryModel,
    FuturesQuote,
)
from core.utils.logging import configure_logging, get_logger  # noqa: E402
from core.utils.tracking import run  # noqa: E402
from forward.models import SchwartzParams  # noqa: E402
from p04_forward_adapter import DAYS_PER_YEAR, P04ForwardAdapter  # noqa: E402

log = get_logger("run_pricing")

RESULTS = Path(__file__).resolve().parents[1] / "results"

GPU = "H100"
RATE = DEFAULT_RISK_FREE_RATE  # annualized financing rate (assumption)
CONVENIENCE_YIELD = 0.01  # exogenous convenience yield (PoC assumption, not observable)
MATURITIES_DAYS = [30.0, 90.0, 180.0, 360.0]
# Schwartz forward curve: assumed parameters (no real calibration here).
SCHWARTZ = SchwartzParams(kappa=0.05, theta=2.5, sigma=0.3)
ASSUMED_SPOT_USD = 2.50  # documented fallback if no real snapshot is available

DISCLAIMER = (
    "THEORETICAL/SIMULATED — compute futures (SDH100RT settlement) are not listed. "
    "The forward comes from a model (Schwartz/carry), never from an observed market."
)


def load_real_spot() -> tuple[float, str]:
    """Real compute spot via ``core.ingestion``; **logged** fallback otherwise.

    Returns
    -------
    tuple[float, str]
        ``(spot_usd_per_gpu_h, source)`` where ``source`` distinguishes real from fallback.
    """
    try:
        from core.ingestion import CsvSnapshotStore, build_spot_index
        from core.utils.config import SNAPSHOTS_DIR

        snapshots = CsvSnapshotStore(SNAPSHOTS_DIR).load()
        if not snapshots:
            raise FileNotFoundError(f"no snapshots under {SNAPSHOTS_DIR}")
        point = build_spot_index(snapshots, dt.datetime.now(dt.timezone.utc), GPU)
        log.info(
            "Real spot %s = %.4f $/GPU·h (%d venues)",
            GPU,
            point.price_usd_per_hour,
            point.n_sources,
        )
        return point.price_usd_per_hour, "real:compute_index"
    except Exception as exc:  # noqa: BLE001 - documented fallback, never silent
        log.warning(
            "Real spot unavailable (%s) — falling back to assumption %.2f $/GPU·h",
            exc,
            ASSUMED_SPOT_USD,
        )
        return ASSUMED_SPOT_USD, "assumed_fallback"


def _row(tau_days: float, carry: FuturesQuote, p04: FuturesQuote) -> dict[str, float]:
    return {
        "maturity_days": tau_days,
        "tau_years": carry.maturity_years,
        "carry_forward": carry.forward,
        "carry_basis": carry.basis,
        "carry_d_forward_d_tau": carry.sensitivities.d_forward_d_tau,
        "p04_forward": p04.forward,
        "p04_basis": p04.basis,
        "p04_implied_convenience_yield": p04.convenience_yield,
    }


def main() -> None:
    spot, spot_source = load_real_spot()

    carry_pricer = CarryFuturesPricer(
        CostOfCarryModel(rate=RATE, convenience_yield=CONVENIENCE_YIELD), rate=RATE
    )
    p04_pricer = CarryFuturesPricer(P04ForwardAdapter(SCHWARTZ), rate=RATE)

    term_structure = [
        _row(
            tau_days,
            carry_pricer.price(spot, tau_days / DAYS_PER_YEAR),
            p04_pricer.price(spot, tau_days / DAYS_PER_YEAR),
        )
        for tau_days in MATURITIES_DAYS
    ]

    params: dict[str, Any] = {
        "gpu": GPU,
        "spot_usd_per_gpu_h": spot,
        "spot_source": spot_source,
        "rate_annual": RATE,
        "carry_convenience_yield": CONVENIENCE_YIELD,
        "forward_model": "schwartz_analytic+cost_of_carry",
        "schwartz_kappa": SCHWARTZ.kappa,
        "schwartz_theta": SCHWARTZ.theta,
        "schwartz_sigma": SCHWARTZ.sigma,
        "maturities_days": ",".join(str(int(m)) for m in MATURITIES_DAYS),
        "simulated": True,
    }

    with run("p06_compute_futures_pricing", params):
        for row in term_structure:
            d = int(row["maturity_days"])
            mlflow.log_metric(f"carry_basis_{d}d", row["carry_basis"])
            mlflow.log_metric(f"p04_basis_{d}d", row["p04_basis"])
            mlflow.log_metric(f"p04_implied_yield_{d}d", row["p04_implied_convenience_yield"])

    RESULTS.mkdir(parents=True, exist_ok=True)
    summary = {
        "disclaimer": DISCLAIMER,
        "simulated": True,
        "params": params,
        "term_structure": term_structure,
    }
    (RESULTS / "futures_pricing_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    log.info(
        "Spot=%.4f $/GPU·h (%s) | P04 base 360d=%.4f | implied yield 360d=%.4f",
        spot,
        spot_source,
        term_structure[-1]["p04_basis"],
        term_structure[-1]["p04_implied_convenience_yield"],
    )
    log.info("Summary written: %s — %s", RESULTS / "futures_pricing_summary.json", DISCLAIMER)


if __name__ == "__main__":
    configure_logging()
    main()
