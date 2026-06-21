"""Démo reproductible du moteur P08 sur fixtures synthétiques → run MLflow complet.

Exécute la stratégie de mean-reversion sur la série synthétique, calcule les métriques
de risque et logge un run MLflow complet (params + métriques + SHA git + version DVC
+ figure du PnL) dans `results/mlruns`. Rejouable à l'identique (graine fixée).

    uv run python projects/08_backtest_risk_engine/run_demo.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import mlflow

from core.backtest import BacktestEngine, LinearCostModel, cumulative_pnl
from core.backtest.tracking import dvc_version, log_metrics, log_pnl_figure, tracked_run

_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE / "src"))
import demo_fixtures  # noqa: E402  (ajout dynamique au sys.path ci-dessus)

RESULTS_DIR = _HERE / "results"
EXPERIMENT = "p08_backtest_demo"


def main() -> None:
    prices = demo_fixtures.synthetic_prices()
    strategy = demo_fixtures.ZScoreMeanReversion(window=32, z_scale=2.0)
    cost_model = LinearCostModel(fees_bps=10.0, slippage_bps=5.0)
    engine = BacktestEngine(cost_model=cost_model, periods_per_year=252.0)

    params = {
        "strategy": "zscore_mean_reversion",
        "window": strategy.window,
        "z_scale": strategy.z_scale,
        "fees_bps": cost_model.fees_bps,
        "slippage_bps": cost_model.slippage_bps,
        "periods_per_year": 252.0,
        "seed": demo_fixtures.DEMO_SEED,
        "n_obs": int(prices.shape[0]),
        "n_trials": 1,  # multiple testing : 1 seule config essayée (pitfall overfitting)
    }

    result = engine.run(prices, strategy, params=params)

    # Tracking local fichier dans le module (convergence pourra relocaliser vers
    # experiments/ et choisir un backend non-déprécié à l'échelle du labo).
    os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")
    mlflow.set_tracking_uri((RESULTS_DIR / "mlruns").as_uri())
    with tracked_run(EXPERIMENT, params):
        log_metrics(result.metrics)
        log_pnl_figure(cumulative_pnl(result.ledger.pnl))
        run_id = mlflow.active_run().info.run_id

    snapshot = {
        "run_id": run_id,
        "dvc_version": dvc_version(),
        "params": params,
        "metrics": result.metrics,
    }
    (RESULTS_DIR / "last_run.json").write_text(json.dumps(snapshot, indent=2), encoding="utf-8")

    print(f"run_id={run_id}  dvc_version={snapshot['dvc_version']}")
    for name, value in result.metrics.items():
        print(f"  {name:14s} = {value:.6f}")


if __name__ == "__main__":
    main()
