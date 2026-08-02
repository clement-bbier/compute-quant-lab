"""Executable entry point: builds and logs a SIMULATED compute forward curve.

Usage:
    uv run python projects/04_compute_index_curve/run_build_curve.py

Pipeline: (1) current spot via the index if real snapshots exist
(``data/snapshots/``), else demo spot; (2) calibration of the Schwartz parameters
on the log-spot history; (3) simulation of the forward curve (Rust engine
if built, else Python MC); (4) logged **MLflow run** (params + git SHA).

Warning: the produced curve is ALWAYS ``simulated=True``: the compute futures (settlement
on the Silicon Data SDH100RT index) are not listed. While the snapshot series remains
thin, the calibration history below is synthetic (clearly labeled); it will
suffice to replace it with the real index series once collection has accumulated.
"""

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

# Lab convention: local file-based MLflow tracking. MLflow 2026 requires this opt-in.
os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")
_ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("MLFLOW_TRACKING_URI", (_ROOT / "experiments" / "mlruns").as_uri())
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from core.ingestion import CsvSnapshotStore, InsufficientDataError, build_spot_index  # noqa: E402
from core.utils.logging import configure_logging, get_logger  # noqa: E402
from forward.build_curve import build_forward_curve  # noqa: E402

logger = get_logger("run_build_curve")

SNAPSHOT_DIR = _ROOT / "data" / "snapshots"
RESULTS_DIR = Path(__file__).resolve().parent / "results"
GPU_MODEL = "H100"
MATURITIES = [0.0, 7.0, 30.0, 90.0, 180.0, 360.0]


def _current_spot() -> float:
    """Current spot via the index on real snapshots, else a demo value."""
    snapshots = CsvSnapshotStore(SNAPSHOT_DIR).load()
    if snapshots:
        try:
            now = max(s.snapshotted_at for s in snapshots)
            point = build_spot_index(snapshots, now, GPU_MODEL)
            logger.info(
                "Real index spot: %.4f $/GPU·h (%s)", point.price_usd_per_hour, point.method
            )
            return point.price_usd_per_hour
        except InsufficientDataError:
            logger.warning("Snapshots present but insufficient: falling back to demo spot.")
    return 2.30


def _demo_log_history(spot: float, n: int = 180, seed: int = 7) -> list[float]:
    """Synthetic mean-reverting log-spot history (placeholder, demo-labeled)."""
    import numpy as np

    rng = np.random.default_rng(seed)
    kappa, sigma, dt_days = 0.05, 0.06, 1.0
    ln_theta = math.log(spot)
    decay = math.exp(-kappa * dt_days)
    sd = math.sqrt((sigma**2 / (2 * kappa)) * (1 - math.exp(-2 * kappa * dt_days)))
    x = [ln_theta]
    for _ in range(n - 1):
        x.append(decay * x[-1] + (1 - decay) * ln_theta + sd * float(rng.standard_normal()))
    return x


def main() -> None:
    spot = _current_spot()
    history = _demo_log_history(spot)
    curve = build_forward_curve(history, spot=spot, maturities_days=MATURITIES)

    logger.info(
        "SIMULATED forward curve (%s, seed=%s, n_paths=%s):",
        curve.model_name,
        curve.seed,
        curve.n_paths,
    )
    for point in curve.points:
        logger.info("  τ=%6.1f d -> %.4f $/GPU·h", point.maturity_days, point.forward_price)
    logger.info(
        "Run logged under %s (experiment 'compute_forward_curve').",
        os.environ["MLFLOW_TRACKING_URI"],
    )

    summary = {
        "spot": curve.spot,
        "simulated": curve.simulated,
        "model_name": curve.model_name,
        "seed": curve.seed,
        "n_paths": curve.n_paths,
        "kappa": curve.params.kappa,
        "theta": curve.params.theta,
        "sigma": curve.params.sigma,
        "points": [
            {"maturity_days": p.maturity_days, "forward_price": p.forward_price}
            for p in curve.points
        ],
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "run_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    logger.info("Summary written: %s", RESULTS_DIR / "run_summary.json")


if __name__ == "__main__":
    configure_logging()
    main()
