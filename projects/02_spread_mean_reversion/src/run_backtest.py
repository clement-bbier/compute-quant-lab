"""Headline P02 run: cointegration -> z-score signal -> P08 backtest -> reproducible MLflow run.

Pipeline wired to **real** data: ENTSO-E energy (`load_energy_entsoe`) + compute index
reconstructed from real marketplace snapshots (`compute_index_series`). While the ENTSO-E token
or the compute history are missing, we fall back to an **explicitly simulated** dataset (provenance
``simulated=True``, rule ``forward-real-simulated``) to validate the pipeline — never sold
as alpha. The run logs to MLflow: params (z-thresholds, lookback, costs, n_trials, cointegration
p-value, half-life, real/simulated) + risk metrics + PnL figure. Replayable (fixed seed).

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
from core.backtest.tracking import log_metrics, log_pnl_figure, tracked_run
from core.ingestion import CsvSnapshotStore
from core.utils.logging import configure_logging, get_logger

_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE))
import cointegration  # noqa: E402  (src added to sys.path above)
from data_sources import DataProvenance, SpreadDataset, build_spread, compute_index_series  # noqa: E402
from strategy import MeanReversionStrategy  # noqa: E402

log = get_logger("run_backtest")

# Repo root: this file lives at projects/02_spread_mean_reversion/src/.
_REPO_ROOT = Path(__file__).resolve().parents[3]
RESULTS_DIR = _HERE.parent / "results"
EXPERIMENT = "p02_spread_mean_reversion"
SEED = 42
GPU, REGION = "H100", "FR"
PERIODS_PER_YEAR = 8760.0  # ENTSO-E hourly grid

# Thresholds fixed *a priori* (not optimized) -> n_trials = 1 (anti multiple-testing, backtest-pitfalls).
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
    """Two legs **cointegrated by construction**, **stationary** P01 economic spread.

    Energy is an I(1) random walk (EUR/MWh). Compute = energy cost + OU spread:
    ``compute - energy_cost`` is therefore exactly a stationary OU process (clean mean reversion, positive,
    ~2.3 $/GPU·h realistic for H100), and compute<->energy are cointegrated. Strictly simulated.
    """
    rng = np.random.default_rng(SEED)
    idx = pd.date_range("2025-01-01", periods=n, freq="h", tz="UTC")
    energy = np.clip(120.0 + np.cumsum(rng.standard_normal(n) * 3.0), 20.0, None)
    # P01 energy cost (8x H100 @ 700 W TDP, PUE 1.82) reproduced so the spread = pure OU.
    power_kw_per_gpu, pue = 700.0 / 1000.0, 1.82
    energy_cost = power_kw_per_gpu * pue * energy / 1000.0
    # Spread = pure stationary OU. NB: the strategy then tracks the process exactly -> inflated
    # synthetic Sharpe (backtest illusion, cf. results/SYNTHESIS.md). Used to validate the PIPELINE.
    spread_ou = _ou(n, theta=0.05, sigma=0.10, rng=rng, mu=2.3)
    compute = energy_cost + spread_ou
    return (
        pd.DataFrame({REGION: energy}, index=idx),
        pd.DataFrame({GPU: compute}, index=idx),
    )


def _load_legs() -> tuple[pd.DataFrame, pd.DataFrame, DataProvenance]:
    """Loads both real legs if available, otherwise falls back to the labeled simulated dataset.

    Energy tries the committed cold store first (zero key required), then a live ENTSO-E
    call if a token is set (see ``data_sources.load_energy_entsoe``). Compute still requires
    accumulated marketplace snapshots — no cold store for it yet, so the energy window is
    bounded to the snapshots' own coverage: stretching energy back to 2024 while compute only
    exists for the last accumulated month would ffill a "flat" compute price across 2+ empty
    years (degenerate, near-collinear series -- cointegration tests fail to converge on it),
    not a meaningful real-data run.
    """
    from data_sources import load_energy_entsoe

    snapshots_dir = _REPO_ROOT / "data" / "snapshots"
    snapshots = CsvSnapshotStore(snapshots_dir).load()
    if not snapshots:
        log.warning(
            "No compute snapshot found in %s — falling back to the simulated dataset.",
            snapshots_dir,
        )
        energy_df, compute_df = _simulated_legs()
        return (
            energy_df,
            compute_df,
            DataProvenance(source="synthetic_cointegrated_ou", simulated=True),
        )

    window_start = pd.Timestamp(min(s.snapshotted_at for s in snapshots)).tz_convert("UTC")
    window_end = pd.Timestamp(max(s.snapshotted_at for s in snapshots)).tz_convert("UTC")
    try:
        energy, energy_source = load_energy_entsoe(REGION, window_start, window_end)
    except RuntimeError as exc:
        log.warning(
            "No real energy data available (%s) — falling back to the simulated dataset.", exc
        )
        energy_df, compute_df = _simulated_legs()
        return (
            energy_df,
            compute_df,
            DataProvenance(source="synthetic_cointegrated_ou", simulated=True),
        )

    compute = compute_index_series(snapshots, energy.index, GPU)
    energy_df = pd.DataFrame({REGION: energy})
    compute_df = pd.DataFrame({GPU: compute}).dropna()
    return (
        energy_df,
        compute_df,
        DataProvenance(source=f"{energy_source}+marketplace", simulated=False),
    )


def _cointegration_diagnostics(
    energy: pd.Series, compute: pd.Series, dataset: SpreadDataset
) -> dict[str, float | bool]:
    """Tests energy<->compute cointegration (Engle-Granger + Johansen) and the spread half-life."""
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
    # Diagnostics run on the same aligned grid as the spread itself (dataset.spread's index):
    # energy_df/compute_df can differ in length (compute is only observed at fresh-snapshot
    # instants) -- engle_granger requires equal-length series, so reindex onto the P01-aligned
    # grid rather than passing the raw, differently-shaped inputs.
    aligned_index = dataset.spread.index
    energy_aligned = energy_df[REGION].reindex(aligned_index)
    compute_aligned = compute_df[GPU].reindex(aligned_index)
    diagnostics = _cointegration_diagnostics(energy_aligned, compute_aligned, dataset)

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
        "n_trials": 1,  # thresholds fixed a priori: no search -> no multiple-testing
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
        "params": params,
        "metrics": result.metrics,
        "n_trades": result.ledger.n_trades,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "last_run.json").write_text(
        json.dumps(snapshot, indent=2, default=str), encoding="utf-8"
    )

    log.info("run_id=%s  simulated=%s  source=%s", run_id, provenance.simulated, provenance.source)
    log.info(
        "cointegration p-value=%.4f  half-life=%.1fh  johansen_relations=%s",
        diagnostics["coint_pvalue"],
        diagnostics["half_life_hours"],
        diagnostics["johansen_n_relations"],
    )
    for name, value in result.metrics.items():
        log.info("  %-14s = %.6f", name, value)


if __name__ == "__main__":
    configure_logging()
    main()
