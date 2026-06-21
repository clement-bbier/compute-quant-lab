"""Run de démonstration du pricer du digital spark spread (P01), loggué MLflow.

Charge le dataset aligné (``data/interim/aligned_spark.parquet``), price le spread
via le pricer vectoriel point-in-time (oracle Python ou noyau Rust si compilé),
loggue params + métriques + SHA git dans MLflow, et dépose un résumé JSON dans
``results/`` pour la synthèse.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path

# MLflow ≥ 3 met le file store en « maintenance mode » : on opte explicitement
# pour le backend fichier (convention locale du labo, cf. experiments/mlruns).
os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")

import mlflow  # noqa: E402 - après l'opt-out file-store ci-dessus
import pandas as pd  # noqa: E402

from core.pricing import (
    ConstantFx,
    DataFramePriceSource,
    ServerPowerModel,
    SparkSpreadPricer,
    SpreadResult,
)
from core.utils.tracking import run

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("run_pricer")

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA = REPO_ROOT / "data" / "interim" / "aligned_spark.parquet"
RESULTS = Path(__file__).resolve().parents[1] / "results"

REGION = "FR"
GPU = "H100"
# Hypothèses physiques (8x H100) et change — alignées sur la thèse du labo.
TDP_W = 700.0
PUE = 1.82
N_GPUS = 8
FX_EUR_PER_USD = 0.92


def _build_source(frame: pd.DataFrame) -> DataFramePriceSource:
    return DataFramePriceSource(
        energy=frame[["energy_eur_per_mwh"]].rename(columns={"energy_eur_per_mwh": REGION}),
        compute=frame[["compute_usd_per_gpu_h"]].rename(columns={"compute_usd_per_gpu_h": GPU}),
    )


def _metrics(result: SpreadResult) -> dict[str, float]:
    spread = result.spread.dropna()
    return {
        "spread_mean_eur": float(spread.mean()),
        "spread_std_eur": float(spread.std()),
        "spread_min_eur": float(spread.min()),
        "spread_max_eur": float(spread.max()),
        "spread_positive_share": float((spread > 0).mean()),
        "revenue_mean_eur": float(result.revenue.dropna().mean()),
        "cost_mean_eur": float(result.cost.dropna().mean()),
        "n_obs": float(len(spread)),
    }


def _dvc_version(path: Path) -> str:
    dvc_file = path.with_suffix(path.suffix + ".dvc")
    if not dvc_file.exists():
        return "untracked"
    try:
        return subprocess.check_output(
            ["dvc", "get-url", str(dvc_file)], cwd=REPO_ROOT, text=True
        ).strip() or dvc_file.read_text(encoding="utf-8")[:200]
    except Exception:  # noqa: BLE001 - best effort
        return dvc_file.read_text(encoding="utf-8")[:200]


def main() -> None:
    if not DATA.exists():
        raise SystemExit(f"Dataset absent : {DATA}. Lance d'abord prepare_dataset.py.")

    frame = pd.read_parquet(DATA)
    energy_source = frame.attrs.get("energy_source", "unknown")

    pricer = SparkSpreadPricer(
        ServerPowerModel(tdp_w=TDP_W, pue=PUE, n_gpus=N_GPUS),
        ConstantFx(FX_EUR_PER_USD),
    )
    result = pricer.price(_build_source(frame), gpu=GPU, region=REGION)
    metrics = _metrics(result)

    params = {
        "region": REGION,
        "gpu": GPU,
        "tdp_w": TDP_W,
        "pue": PUE,
        "n_gpus": N_GPUS,
        "fx_eur_per_usd": FX_EUR_PER_USD,
        "kernel": type(pricer._kernel).__name__,  # noqa: SLF001 - introspection démo
        "energy_source": energy_source,
        "window_start": str(result.window[0]),
        "window_end": str(result.window[1]),
        "dvc_data_version": _dvc_version(DATA),
    }

    # MLflow en local sous experiments/mlruns (gitignored), via le util du labo.
    mlflow.set_tracking_uri((REPO_ROOT / "experiments" / "mlruns").as_uri())
    with run("p01_spark_spread_pricer", params):
        for key, value in metrics.items():
            mlflow.log_metric(key, value)

    RESULTS.mkdir(parents=True, exist_ok=True)
    summary = {"params": params, "metrics": metrics}
    (RESULTS / "run_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    log.info("Spread moyen=%.4f €/GPU·h | %% positif=%.1f%% | n=%d",
             metrics["spread_mean_eur"], 100 * metrics["spread_positive_share"],
             int(metrics["n_obs"]))
    log.info("Résumé écrit : %s", RESULTS / "run_summary.json")


if __name__ == "__main__":
    main()
