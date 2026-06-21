"""Run headline P02 : cointégration → signal z-score → backtest P08 → run MLflow reproductible.

Pipeline branché sur du **réel** : énergie ENTSO-E (`load_energy_entsoe`) + indice compute
reconstruit des snapshots marketplace réels (`compute_index_series`). Tant que le token ENTSO-E
ou l'historique compute manquent, on bascule sur un jeu **explicitement simulé** (provenance
``simulated=True``, rule ``forward-real-simulated``) pour valider le pipeline — jamais vendu
comme alpha. Le run logge MLflow : params (seuils z, lookback, coûts, n_trials, p-value de
cointégration, demi-vie, réel/simulé) + métriques de risque + figure PnL. Rejouable (graine fixée).

    uv run python projects/02_spread_mean_reversion/src/run_backtest.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import mlflow
import numpy as np
import pandas as pd

from core.backtest import BacktestEngine, LinearCostModel, cumulative_pnl
from core.backtest.tracking import dvc_version, log_metrics, log_pnl_figure, tracked_run
from core.ingestion import CsvSnapshotStore

_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE))
import cointegration  # noqa: E402  (src ajouté au sys.path ci-dessus)
from data_sources import DataProvenance, SpreadDataset, build_spread, compute_index_series  # noqa: E402
from strategy import MeanReversionStrategy  # noqa: E402

RESULTS_DIR = _HERE.parent / "results"
EXPERIMENT = "p02_spread_mean_reversion"
SEED = 42
GPU, REGION = "H100", "FR"
PERIODS_PER_YEAR = 8760.0  # grille horaire ENTSO-E

# Seuils fixés *a priori* (non optimisés) → n_trials = 1 (anti multiple-testing, backtest-pitfalls).
Z_ENTRY, Z_EXIT, LOOKBACK = 2.0, 0.5, 48
FEES_BPS, SLIPPAGE_BPS = 10.0, 5.0


def _ou(
    n: int, *, theta: float, sigma: float, rng: np.random.Generator, mu: float = 0.0
) -> np.ndarray:
    x = np.empty(n, dtype=np.float64)
    x[0] = mu
    for t in range(1, n):
        x[t] = x[t - 1] + theta * (mu - x[t - 1]) + sigma * rng.standard_normal()
    return x


def _simulated_legs(n: int = 2000) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Deux jambes **cointégrées par construction**, spread économique P01 **stationnaire**.

    L'énergie est une marche aléatoire I(1) (€/MWh). Le compute = coût énergétique + spread OU :
    ``compute - coût_énergie`` est donc exactement un OU stationnaire (mean-reversion propre, positif,
    ~2.3 $/GPU·h réaliste H100), et compute↔energy sont cointégrés. Strictement simulé.
    """
    rng = np.random.default_rng(SEED)
    idx = pd.date_range("2025-01-01", periods=n, freq="h", tz="UTC")
    energy = np.clip(120.0 + np.cumsum(rng.standard_normal(n) * 3.0), 20.0, None)
    # Coût énergétique P01 (8x H100 @ 700 W TDP, PUE 1.82) reproduit pour que le spread = OU pur.
    power_kw_per_gpu, pue = 700.0 / 1000.0, 1.82
    energy_cost = power_kw_per_gpu * pue * energy / 1000.0
    # Spread = OU stationnaire pur. NB : la stratégie épouse alors exactement le processus → Sharpe
    # synthétique élevé (illusion de backtest, cf. results/SYNTHESIS.md). Sert à valider le PIPELINE.
    spread_ou = _ou(n, theta=0.05, sigma=0.10, rng=rng, mu=2.3)
    compute = energy_cost + spread_ou
    return (
        pd.DataFrame({REGION: energy}, index=idx),
        pd.DataFrame({GPU: compute}, index=idx),
    )


def _load_legs() -> tuple[pd.DataFrame, pd.DataFrame, DataProvenance]:
    """Charge les deux jambes réelles si disponibles, sinon bascule sur le jeu simulé étiqueté."""
    token = os.environ.get("ENTSOE_API_TOKEN")
    snapshots = CsvSnapshotStore(Path("data/snapshots")).load()
    if token and snapshots:
        from data_sources import load_energy_entsoe  # import tardif : réseau token-gated

        energy = load_energy_entsoe(
            REGION, pd.Timestamp("2024-01-01Z"), pd.Timestamp("2025-01-01Z")
        )
        compute = compute_index_series(snapshots, energy.index, GPU)
        energy_df = pd.DataFrame({REGION: energy})
        compute_df = pd.DataFrame({GPU: compute}).dropna()
        return energy_df, compute_df, DataProvenance(source="entsoe+marketplace", simulated=False)
    energy_df, compute_df = _simulated_legs()
    return energy_df, compute_df, DataProvenance(source="synthetic_cointegrated_ou", simulated=True)


def _cointegration_diagnostics(
    energy: pd.Series, compute: pd.Series, dataset: SpreadDataset
) -> dict[str, float | bool]:
    """Teste la cointégration énergie↔compute (Engle-Granger + Johansen) et la demi-vie du spread."""
    eg = cointegration.engle_granger(compute, energy)
    johansen = cointegration.johansen(pd.concat([compute, energy], axis=1))
    return {
        "coint_pvalue": eg.pvalue,
        "is_cointegrated": eg.is_cointegrated,
        "hedge_ratio": eg.hedge_ratio,
        "johansen_n_relations": johansen.n_relations,
        "half_life_hours": cointegration.half_life(dataset.spread),
    }


def main() -> None:
    energy_df, compute_df, provenance = _load_legs()
    dataset = build_spread(energy_df, compute_df, gpu=GPU, region=REGION, provenance=provenance)
    diagnostics = _cointegration_diagnostics(energy_df[REGION], compute_df[GPU], dataset)

    strategy = MeanReversionStrategy(z_entry=Z_ENTRY, z_exit=Z_EXIT, lookback=LOOKBACK)
    engine = BacktestEngine(
        cost_model=LinearCostModel(fees_bps=FEES_BPS, slippage_bps=SLIPPAGE_BPS),
        periods_per_year=PERIODS_PER_YEAR,
    )
    spread = dataset.spread.to_numpy()

    params = {
        "strategy": "mean_reversion_hysteresis",
        "z_entry": Z_ENTRY,
        "z_exit": Z_EXIT,
        "lookback": LOOKBACK,
        "fees_bps": FEES_BPS,
        "slippage_bps": SLIPPAGE_BPS,
        "periods_per_year": PERIODS_PER_YEAR,
        "seed": SEED,
        "n_obs": int(spread.shape[0]),
        "n_trials": 1,  # seuils fixés a priori : pas de recherche → pas de multiple-testing
        "gpu": GPU,
        "region": REGION,
        "data_source": provenance.source,
        "simulated": provenance.simulated,
        **diagnostics,
    }
    result = engine.run(spread, strategy, params=params)

    os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")
    mlflow.set_tracking_uri((RESULTS_DIR / "mlruns").as_uri())
    with tracked_run(EXPERIMENT, params):
        log_metrics(result.metrics)
        log_pnl_figure(cumulative_pnl(result.ledger.pnl))
        mlflow.set_tag("simulated", str(provenance.simulated))
        run_id = mlflow.active_run().info.run_id

    snapshot = {
        "run_id": run_id,
        "dvc_version": dvc_version(),
        "params": params,
        "metrics": result.metrics,
        "n_trades": result.ledger.n_trades,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "last_run.json").write_text(
        json.dumps(snapshot, indent=2, default=str), encoding="utf-8"
    )

    print(f"run_id={run_id}  simulated={provenance.simulated}  source={provenance.source}")
    print(
        f"cointegration p-value={diagnostics['coint_pvalue']:.4f}  "
        f"half-life={diagnostics['half_life_hours']:.1f}h  "
        f"johansen_relations={diagnostics['johansen_n_relations']}"
    )
    for name, value in result.metrics.items():
        print(f"  {name:14s} = {value:.6f}")


if __name__ == "__main__":
    main()
