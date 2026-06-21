"""Run headline P10 : signaux mockés → portefeuille → exécution → backtest P08 → run MLflow.

Pipeline desk de bout en bout sur des **signaux mockés** (placeholders P02/P06/P09). Les vrais
producteurs se brancheront en convergence sans changer ce code (OCP). La série de prix desk est
**explicitement simulée** (rule ``forward-real-simulated``) : aucun alpha n'est revendiqué — le
but est de valider le PIPELINE (pondération sous risque + coûts d'exécution → PnL net).

Le run logge MLflow : params (pondération, coûts, κ, signaux utilisés, n_trials, simulated) +
métriques de risque **nettes ET brutes** + contribution par signal + figure du PnL net. Rejouable
(graine fixée). Lancer :

    uv run python projects/10_portfolio_execution/src/run_desk.py
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

import mlflow
import numpy as np

from core.backtest import BacktestEngine, LinearCostModel, cumulative_pnl
from core.backtest.metrics import DefaultMetrics
from core.backtest.protocols import FloatArray, Ledger
from core.backtest.tracking import dvc_version, log_pnl_figure, tracked_run

_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE))
from desk import DeskStrategy  # noqa: E402  (src ajouté au sys.path ci-dessus)
from execution import ExecutionModel  # noqa: E402
from portfolio import PortfolioConstructor  # noqa: E402
from provenance import SignalProvenance  # noqa: E402
from signals import ConstantMock, MeanReversionMock, MomentumMock, SignalProducer  # noqa: E402

RESULTS_DIR = _HERE.parent / "results"
EXPERIMENT = "p10_portfolio_execution"
SEED = 42
PERIODS_PER_YEAR = 252.0  # desk à pas journalier (démo)
CAPITAL = 1.0

# Paramètres desk fixés *a priori* (non optimisés) → n_trials = 1 (anti multiple-testing).
VOL_LOOKBACK, VOL_FLOOR, GROSS_CAP = 60, 1e-4, 1.0
FEES_BPS, SLIPPAGE_BPS, IMPACT_KAPPA = 10.0, 5.0, 0.02
KAPPA_GRID = [0.0, 0.01, 0.02, 0.05, 0.1]


def DEFAULT_PRODUCERS() -> list[SignalProducer]:
    """Trois signaux mockés disjoints (carry, mean-reversion, momentum) — placeholders P02/P06/P09."""
    return [
        ConstantMock(1.0, name="carry_mock"),
        MeanReversionMock(lookback=20, name="mean_reversion_mock"),
        MomentumMock(lookback=40, name="momentum_mock"),
    ]


def _ou(n: int, *, theta: float, sigma: float, rng: np.random.Generator) -> FloatArray:
    """Processus d'Ornstein-Uhlenbeck stationnaire (oscillation → matière à la mean-reversion)."""
    x = np.empty(n, dtype=np.float64)
    x[0] = 0.0
    for t in range(1, n):
        x[t] = x[t - 1] - theta * x[t - 1] + sigma * rng.standard_normal()
    return x


def build_synthetic_prices(n: int, seed: int) -> tuple[FloatArray, SignalProvenance]:
    """Série de prix desk **simulée** : tendance lente (momentum) + oscillation OU (mean-reversion).

    Strictement synthétique et étiquetée ``simulated=True`` : sert à valider le pipeline, jamais
    vendue comme un sous-jacent réel.
    """
    rng = np.random.default_rng(seed)
    trend = np.linspace(0.0, 15.0, n)
    oscillation = _ou(n, theta=0.08, sigma=1.0, rng=rng)
    noise = rng.standard_normal(n) * 0.2
    prices = np.clip(100.0 + trend + oscillation + noise, 1.0, None).astype(np.float64)
    return prices, SignalProvenance(name="synthetic_desk", simulated=True)


@dataclass(frozen=True)
class DeskResult:
    """Résultat du backtest desk : comptabilité brute/nette + métriques + attribution par signal."""

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
    """Run du moteur P08 **sans coût** (les coûts sont appliqués ensuite) → ledger brut + desk."""
    desk = DeskStrategy(producers, constructor, vol_lookback=VOL_LOOKBACK)
    engine = BacktestEngine(
        cost_model=LinearCostModel(0.0, 0.0), periods_per_year=periods_per_year, capital=CAPITAL
    )
    return engine.run(prices, desk).ledger, desk


def _net_ledger(gross: Ledger, net_returns: FloatArray) -> Ledger:
    """Reconstruit un ledger **net** (mêmes positions, rendements nets de coûts)."""
    net_pnl = net_returns * CAPITAL
    return Ledger(
        returns=net_returns,
        pnl=net_pnl,
        equity_curve=CAPITAL + np.cumsum(net_pnl),
        positions=gross.positions,
        n_trades=gross.n_trades,
    )


def _attribution(desk: DeskStrategy, producers: list[SignalProducer]) -> dict[str, float]:
    """Contribution de chaque signal au PnL brut : Σ_t composante_i[t-1]·rendement_marché[t]."""
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
    """Backtest desk complet : run brut P08 → coûts d'exécution → métriques nettes + attribution."""
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
    """Sensibilité du PnL net au coefficient d'impact κ (le run brut, lui, ne dépend pas des coûts)."""
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
        "n_trials": 1,  # params fixés a priori : pas de recherche → pas de multiple-testing
        "signals": ",".join(p.name for p in producers),
        "data_source": "synthetic_desk",
        "simulated": True,
    }


def main() -> None:
    prices, provenance = build_synthetic_prices(n=1500, seed=SEED)
    producers = DEFAULT_PRODUCERS()
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
        "dvc_version": dvc_version(),
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

    print(f"run_id={run_id}  simulated={provenance.simulated}  signals={params['signals']}")
    print(f"  {'metric':16s} {'gross':>12s} {'net':>12s}")
    for name in result.net_metrics:
        print(f"  {name:16s} {result.gross_metrics[name]:12.6f} {result.net_metrics[name]:12.6f}")
    print("  contribution par signal (PnL brut) :")
    for name, value in result.attribution.items():
        print(f"    {name:22s} = {value:+.6f}")


if __name__ == "__main__":
    main()
