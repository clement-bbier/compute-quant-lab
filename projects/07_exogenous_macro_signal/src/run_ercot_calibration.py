"""ERCOT L0 calibration run: Parquet cold store -> run_calibration -> MLflow.

Operational. Reads ``data/cold/ercot`` (versioned in plain git), builds the
point-in-time dataset (predictors rebuilt at ``as_of=6pm D-1``, aligned with the RTM spike
label), runs the calibration (purged CV + climatology baseline + PR-AUC/BH), and logs an
MLflow run (params + git SHA, rules training-cold-store & backtest-mlflow-logging).
**No live data.**

Usage: ``uv run python projects/07_exogenous_macro_signal/src/run_ercot_calibration.py``
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # src/: ercot_dataset, ercot_calibration

import mlflow  # noqa: E402

from core.storage.energy_store import EnergyColdStore  # noqa: E402
from core.utils.logging import get_logger  # noqa: E402
from core.utils.tracking import run  # noqa: E402
from ercot_calibration import run_calibration  # noqa: E402
from ercot_dataset import build_calibration_dataset  # noqa: E402

log = get_logger("run_ercot_calibration")

# Repo root: this file lives at projects/07_exogenous_macro_signal/src/.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_COLD = _REPO_ROOT / "data" / "cold" / "ercot"


def main() -> None:  # pragma: no cover (operational, reads the real cold store)
    if not _COLD.exists():
        log.warning(
            "ERCOT cold store not found (%s) — the calibration dataset will be empty.", _COLD
        )
    store = EnergyColdStore(_COLD)
    x, y_hod, index = build_calibration_dataset(store, label="hod")
    _, y_abs, _ = build_calibration_dataset(store, label="abs")

    n_hod, n_abs = int(y_hod.sum()), int(y_abs.sum())
    log.info("Dataset: %d aligned rows | spikes hod=%d, abs=%d", len(y_hod), n_hod, n_abs)
    if len(y_hod) < 100 or n_hod < 5:
        log.warning(
            "Small sample / few positives -> result is INDICATIVE (wide CIs, limited power)."
        )

    params = {
        "market": "ercot",
        "predictors": "reserve_margin,net_load_gradient",
        "as_of_utc_hour": 23,
        "n_samples": int(len(y_hod)),
        "n_spikes_hod": n_hod,
        "n_spikes_abs": n_abs,
    }
    with run("ercot_grid_stress_calibration", params):
        results = run_calibration(x, index, {"hod_pct99": y_hod, "abs_1500": y_abs}, n_boot=1000)
        for name, res in results.items():
            log.info("[%s]", name)
            for key, val in res.items():
                mlflow.log_metric(f"{name}__{key}", float(val))
                log.info("  %s: %s", key, val)

    log.info("Run logged to experiments/mlruns (mlflow ui to explore).")


if __name__ == "__main__":  # pragma: no cover
    main()
