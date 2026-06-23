"""Run de calibration L0 ERCOT : cold store Parquet → run_calibration → MLflow.

Opérationnel. Lit ``data/cold/ercot`` (versionné DVC), construit le dataset point-in-time
(prédicteurs reconstruits à ``as_of=18h J-1``, alignés sur le label spike RTM), lance la
calibration (purged CV + baseline climatologique + PR-AUC/BH) et logge un run MLflow
(params + SHA git + version DVC, rules training-cold-store & backtest-mlflow-logging).
**Aucune donnée live.**

Usage : ``uv run python projects/07_exogenous_macro_signal/src/run_ercot_calibration.py``
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # src/ : ercot_dataset, ercot_calibration

import mlflow  # noqa: E402

from core.storage.energy_store import EnergyColdStore  # noqa: E402
from core.utils.tracking import run  # noqa: E402
from ercot_calibration import run_calibration  # noqa: E402
from ercot_dataset import build_calibration_dataset  # noqa: E402

_COLD = Path("data/cold/ercot")


def main() -> None:  # pragma: no cover (opérationnel, lit le cold store réel)
    store = EnergyColdStore(_COLD)
    x, y_hod, index = build_calibration_dataset(store, label="hod")
    _, y_abs, _ = build_calibration_dataset(store, label="abs")

    n_hod, n_abs = int(y_hod.sum()), int(y_abs.sum())
    print(f"Dataset : {len(y_hod)} lignes alignées | spikes hod={n_hod}, abs={n_abs}")
    if len(y_hod) < 100 or n_hod < 5:
        print(
            "⚠️ Échantillon / positifs faibles → résultat INDICATIF (IC larges, puissance limitée)."
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
            print(f"\n[{name}]")
            for key, val in res.items():
                mlflow.log_metric(f"{name}__{key}", float(val))
                print(f"  {key}: {val}")

    print("\n✅ Run loggué dans experiments/mlruns (mlflow ui pour explorer).")


if __name__ == "__main__":  # pragma: no cover
    main()
