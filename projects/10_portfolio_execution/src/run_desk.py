"""P10 headline run: **real** signals → portfolio → execution → P08 backtest → MLflow run.

End-to-end desk pipeline on the **real producers** from ``core.signals`` (mean-reversion
P02, futures basis P06, ML P09) — wired in via ``REAL_PRODUCERS`` without changing the desk's
logic (OCP). ``DEFAULT_PRODUCERS`` (mocks) remains for regression tests. The desk price series is
**explicitly simulated** (rule ``forward-real-simulated``): no alpha is claimed — a flattering
gross on synthetic data is an artifact (see results/SYNTHESIS.md). This validates the PIPELINE
(risk-budgeted weighting + execution costs → net PnL) on real signals.

The run logs to MLflow: params (weighting, costs, κ, signals used, n_trials, simulated) +
risk metrics **both net AND gross** + per-signal contribution + net PnL figure + git SHA.
Replayable (fixed seed). Run:

    uv run python projects/10_portfolio_execution/src/run_desk.py
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import mlflow
import numpy as np
import pandas as pd

from core.backtest import BacktestEngine, LinearCostModel, cumulative_pnl
from core.backtest.metrics import DefaultMetrics
from core.backtest.protocols import FloatArray, Ledger
from core.backtest.tracking import log_pnl_figure, tracked_run
from core.models.pipeline import FeaturePipeline, SpreadFeatureSpec, build_labels
from core.models.protocols import Model
from core.models.validation import (
    PurgedKFold,
    oos_predict,
    sharpe_confidence_interval,
    sharpe_t_stat,
)
from core.models.xgboost_model import SeedBaggingEnsemble, XGBoostDirectionModel
from core.signals import (
    FuturesBasisSignal,
    MeanReversionSignal,
    MLEnsembleSignal,
    SignalProducer,
)
from core.utils.logging import configure_logging, get_logger

_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE))
from desk import DeskStrategy  # noqa: E402  (src added to sys.path above)
from execution import ExecutionModel  # noqa: E402
from portfolio import PortfolioConstructor  # noqa: E402
from provenance import SignalProvenance  # noqa: E402
from signals import ConstantMock, MeanReversionMock, MomentumMock  # noqa: E402

RESULTS_DIR = _HERE.parent / "results"
EXPERIMENT = "p10_portfolio_execution"
log = get_logger("run_desk")
SEED = 42
PERIODS_PER_YEAR = 252.0  # daily-step desk (demo)
CAPITAL = 1.0

# Desk params fixed *a priori* (not optimized) → n_trials = 1 (anti multiple-testing).
VOL_LOOKBACK, VOL_FLOOR, GROSS_CAP = 60, 1e-4, 1.0
FEES_BPS, SLIPPAGE_BPS, IMPACT_KAPPA = 10.0, 5.0, 0.02
KAPPA_GRID = [0.0, 0.01, 0.02, 0.05, 0.1]

# Params for the REAL signals (fixed *a priori*, consistent with P02/P06/P09).
MR_Z_ENTRY, MR_Z_EXIT, MR_LOOKBACK = 2.0, 0.5, 20  # P02: hysteresis z-score
BASIS_TAU, BASIS_LOOKBACK = 0.25, 20  # P06: maturity (years) + carry momentum window
ML_HORIZON, ML_N_SPLITS, ML_NEUTRAL_BAND, ML_N_MEMBERS = 5, 5, 0.05, 3  # P09: OOS purged-CV


def DEFAULT_PRODUCERS() -> list[SignalProducer]:
    """Three disjoint mocked signals (carry, mean-reversion, momentum) — placeholders for P02/P06/P09."""
    return [
        ConstantMock(1.0, name="carry_mock"),
        MeanReversionMock(lookback=20, name="mean_reversion_mock"),
        MomentumMock(lookback=40, name="momentum_mock"),
    ]


def build_ml_proba(
    prices: FloatArray,
    *,
    make_model: Callable[[], Model],
    horizon: int,
    n_splits: int,
) -> FloatArray:
    """Out-of-sample ``P(up)`` probability vector for P09, aligned with ``prices``.

    Faithfully reproduces the P09 pipeline: causal features derived from the series (lags, rolling
    means, momentums) + directional target, then ``oos_predict`` (purged-CV + embargo) with
    the injected model. Non-predictable rows (feature warm-up, tail with no future) stay
    ``NaN`` → the P09 adapter neutralizes them to a flat position. Honesty: the probability is OOS
    (anti-overfit) but **not strictly walk-forward causal** — design assumption inherited from P09.
    """
    n = prices.shape[0]
    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    spread = pd.Series(prices, index=idx)
    spec = SpreadFeatureSpec(lags=(1, 2, 3, 5), rolling_means=(5, 10, 20), momentums=(5, 10))
    features = FeaturePipeline(spread_spec=spec).build_matrix(spread)
    labels = build_labels(spread, horizon=horizon)

    valid = (features.notna().all(axis=1) & labels.notna()).to_numpy()
    proba = np.full(n, np.nan, dtype=np.float64)
    x = features.to_numpy(dtype=np.float64)[valid]
    y = labels.to_numpy(dtype=np.float64)[valid]
    if x.shape[0] < n_splits:
        return proba  # not enough valid samples → stay flat (honest)
    splitter = PurgedKFold(n_splits=n_splits, horizon=horizon, embargo=horizon)
    proba[valid] = oos_predict(make_model, x, y, splitter)
    return proba


def REAL_PRODUCERS(
    prices: FloatArray,
    *,
    seed: int = SEED,
    ml_make_model: Callable[[], Model] | None = None,
    ml_horizon: int = ML_HORIZON,
    ml_n_splits: int = ML_N_SPLITS,
) -> list[SignalProducer]:
    """The 3 **real** producers promoted into ``core.signals``: P02, P06, P09.

    - ``MeanReversionSignal`` (P02): mean reversion of the spread (hysteresis z-score).
    - ``FuturesBasisSignal`` (P06): carry/roll momentum of the future↔spot basis (cost-of-carry).
    - ``MLEnsembleSignal`` (P09): out-of-sample directional ML signal (seed-bagging ensemble).

    At the PoC stage, the desk series is synthetic ⇒ all signals remain labeled ``simulated=True``.
    ``ml_make_model`` allows injecting a lightweight model in tests; XGBoost ensemble by default.
    """
    make_model: Callable[[], Model] = ml_make_model or (
        lambda: SeedBaggingEnsemble(
            make_model=lambda s: XGBoostDirectionModel(random_state=s),
            seeds=tuple(seed + i for i in range(ML_N_MEMBERS)),
        )
    )
    proba = build_ml_proba(prices, make_model=make_model, horizon=ml_horizon, n_splits=ml_n_splits)
    return [
        MeanReversionSignal(
            z_entry=MR_Z_ENTRY,
            z_exit=MR_Z_EXIT,
            lookback=MR_LOOKBACK,
            name="mean_reversion_p02",
            simulated=True,
        ),
        FuturesBasisSignal(tau_years=BASIS_TAU, lookback=BASIS_LOOKBACK, name="futures_basis_p06"),
        MLEnsembleSignal(
            proba, neutral_band=ML_NEUTRAL_BAND, name="ml_ensemble_p09", simulated=True
        ),
    ]


def _ou(n: int, *, theta: float, sigma: float, rng: np.random.Generator) -> FloatArray:
    """Stationary Ornstein-Uhlenbeck process (oscillation → grist for mean-reversion)."""
    x = np.empty(n, dtype=np.float64)
    x[0] = 0.0
    for t in range(1, n):
        x[t] = x[t - 1] - theta * x[t - 1] + sigma * rng.standard_normal()
    return x


def build_synthetic_prices(n: int, seed: int) -> tuple[FloatArray, SignalProvenance]:
    """**Simulated** desk price series: slow trend (momentum) + OU oscillation (mean-reversion).

    Strictly synthetic and labeled ``simulated=True``: used to validate the pipeline, never
    sold as a real underlying.
    """
    rng = np.random.default_rng(seed)
    trend = np.linspace(0.0, 15.0, n)
    oscillation = _ou(n, theta=0.08, sigma=1.0, rng=rng)
    noise = rng.standard_normal(n) * 0.2
    prices = np.clip(100.0 + trend + oscillation + noise, 1.0, None).astype(np.float64)
    return prices, SignalProvenance(name="synthetic_desk", simulated=True)


@dataclass(frozen=True)
class DeskResult:
    """Desk backtest result: gross/net accounting + metrics + per-signal attribution."""

    gross_returns: FloatArray
    net_returns: FloatArray
    costs: FloatArray
    positions: FloatArray
    n_trades: int
    gross_metrics: dict[str, float]
    net_metrics: dict[str, float]
    attribution: dict[str, float] = field(default_factory=dict)


def _gross_run(
    prices: FloatArray,
    producers: list[SignalProducer],
    constructor: PortfolioConstructor,
    periods_per_year: float,
) -> tuple[Ledger, DeskStrategy]:
    """Run the P08 engine **without cost** (costs are applied afterwards) → gross ledger + desk."""
    desk = DeskStrategy(producers, constructor, vol_lookback=VOL_LOOKBACK)
    engine = BacktestEngine(
        cost_model=LinearCostModel(0.0, 0.0), periods_per_year=periods_per_year, capital=CAPITAL
    )
    return engine.run(prices, desk).ledger, desk


def _net_ledger(gross: Ledger, net_returns: FloatArray) -> Ledger:
    """Rebuilds a **net** ledger (same positions, returns net of costs)."""
    net_pnl = net_returns * CAPITAL
    return Ledger(
        returns=net_returns,
        pnl=net_pnl,
        equity_curve=CAPITAL + np.cumsum(net_pnl),
        positions=gross.positions,
        n_trades=gross.n_trades,
    )


def _attribution(desk: DeskStrategy, producers: list[SignalProducer]) -> dict[str, float]:
    """Contribution of each signal to gross PnL: Σ_t component_i[t-1]·market_return[t]."""
    hist = desk.history()
    contrib = (hist.components[:-1] * hist.mkt_returns[1:].reshape(-1, 1)).sum(axis=0)
    return {p.name: float(c) for p, c in zip(producers, contrib)}


def run_desk_backtest(
    prices: FloatArray,
    producers: list[SignalProducer],
    constructor: PortfolioConstructor,
    execution: ExecutionModel,
    *,
    periods_per_year: float,
) -> DeskResult:
    """Full desk backtest: gross P08 run → execution costs → net metrics + attribution."""
    gross_ledger, desk = _gross_run(prices, producers, constructor, periods_per_year)
    net_returns, costs = execution.apply(gross_ledger.returns, gross_ledger.positions)
    metrics = DefaultMetrics(periods_per_year)
    return DeskResult(
        gross_returns=gross_ledger.returns,
        net_returns=net_returns,
        costs=costs,
        positions=gross_ledger.positions,
        n_trades=gross_ledger.n_trades,
        gross_metrics=metrics.compute(gross_ledger),
        net_metrics=metrics.compute(_net_ledger(gross_ledger, net_returns)),
        attribution=_attribution(desk, producers),
    )


def cost_sensitivity(
    prices: FloatArray,
    producers: list[SignalProducer],
    constructor: PortfolioConstructor,
    *,
    kappas: list[float],
    fees_bps: float,
    slippage_bps: float,
    periods_per_year: float,
) -> list[dict[str, float]]:
    """Sensitivity of net PnL to the impact coefficient κ (the gross run itself doesn't depend on costs)."""
    gross_ledger, _ = _gross_run(prices, producers, constructor, periods_per_year)
    metrics = DefaultMetrics(periods_per_year)
    rows: list[dict[str, float]] = []
    for kappa in kappas:
        model = ExecutionModel(fees_bps=fees_bps, slippage_bps=slippage_bps, impact_kappa=kappa)
        net_returns, costs = model.apply(gross_ledger.returns, gross_ledger.positions)
        net_metrics = metrics.compute(_net_ledger(gross_ledger, net_returns))
        rows.append(
            {
                "impact_kappa": kappa,
                "net_pnl_total": net_metrics["pnl_total"],
                "net_sharpe": net_metrics["sharpe"],
                "cost_total": float(costs.sum()),
            }
        )
    return rows


def _build_params(prices: FloatArray, producers: list[SignalProducer]) -> dict[str, object]:
    return {
        "weight_scheme": "inverse_vol",
        "vol_lookback": VOL_LOOKBACK,
        "vol_floor": VOL_FLOOR,
        "gross_cap": GROSS_CAP,
        "fees_bps": FEES_BPS,
        "slippage_bps": SLIPPAGE_BPS,
        "impact_kappa": IMPACT_KAPPA,
        "periods_per_year": PERIODS_PER_YEAR,
        "seed": SEED,
        "n_obs": int(prices.shape[0]),
        "n_trials": 1,  # params fixed a priori: no search → no multiple-testing
        "signals": ",".join(p.name for p in producers),
        "signal_source": "real (P02/P06/P09 via core.signals)",
        "data_source": "synthetic_desk",
        "simulated": True,
    }


def main() -> None:
    prices, provenance = build_synthetic_prices(n=1500, seed=SEED)
    producers = REAL_PRODUCERS(prices, seed=SEED)  # real P02/P06/P09 (mocks → real)
    constructor = PortfolioConstructor(vol_floor=VOL_FLOOR, gross_cap=GROSS_CAP)
    execution = ExecutionModel(
        fees_bps=FEES_BPS, slippage_bps=SLIPPAGE_BPS, impact_kappa=IMPACT_KAPPA
    )

    result = run_desk_backtest(
        prices, producers, constructor, execution, periods_per_year=PERIODS_PER_YEAR
    )
    sensitivity = cost_sensitivity(
        prices,
        producers,
        constructor,
        kappas=KAPPA_GRID,
        fees_bps=FEES_BPS,
        slippage_bps=SLIPPAGE_BPS,
        periods_per_year=PERIODS_PER_YEAR,
    )
    params = _build_params(prices, producers)

    # Printed uncertainty on the net Sharpe (the desk's own "judge on net" policy) --
    # n_obs is the full backtest length, all periods contributing a net-return observation.
    net_sharpe = result.net_metrics["sharpe"]
    n_obs = int(prices.shape[0])
    result.net_metrics["sharpe_t_stat"] = sharpe_t_stat(net_sharpe, n_obs, PERIODS_PER_YEAR)
    ci_lo, ci_hi = sharpe_confidence_interval(net_sharpe, n_obs, PERIODS_PER_YEAR)
    result.net_metrics["sharpe_ci95_lo"] = ci_lo
    result.net_metrics["sharpe_ci95_hi"] = ci_hi

    os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")
    mlflow.set_tracking_uri((RESULTS_DIR / "mlruns").as_uri())
    logged = {
        **{f"net_{k}": v for k, v in result.net_metrics.items()},
        **{f"gross_{k}": v for k, v in result.gross_metrics.items()},
        **{f"contrib_{name}": v for name, v in result.attribution.items()},
        "total_cost": float(result.costs.sum()),
    }
    with tracked_run(EXPERIMENT, params):
        mlflow.log_metrics(logged)
        log_pnl_figure(cumulative_pnl(result.net_returns * CAPITAL))
        mlflow.log_dict({"cost_sensitivity": sensitivity}, "cost_sensitivity.json")
        mlflow.set_tag("simulated", str(provenance.simulated))
        run_id = mlflow.active_run().info.run_id

    snapshot = {
        "run_id": run_id,
        "params": params,
        "net_metrics": result.net_metrics,
        "gross_metrics": result.gross_metrics,
        "attribution": result.attribution,
        "cost_sensitivity": sensitivity,
        "n_trades": result.n_trades,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "last_run.json").write_text(
        json.dumps(snapshot, indent=2, default=str), encoding="utf-8"
    )

    log.info("run_id=%s  simulated=%s  signals=%s", run_id, provenance.simulated, params["signals"])
    log.info("  %-16s %12s %12s", "metric", "gross", "net")
    for name in result.net_metrics:
        if name in result.gross_metrics:
            log.info(
                "  %-16s %12.6f %12.6f", name, result.gross_metrics[name], result.net_metrics[name]
            )
        else:
            log.info("  %-16s %12s %12.6f", name, "-", result.net_metrics[name])
    log.info("  contribution by signal (gross PnL):")
    for name, value in result.attribution.items():
        log.info("    %-22s = %+.6f", name, value)


if __name__ == "__main__":
    configure_logging()
    main()
