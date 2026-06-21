"""Run headline P10 : signaux **réels** → portefeuille → exécution → backtest P08 → run MLflow.

Pipeline desk de bout en bout sur les **vrais producteurs** de ``core.signals`` (mean-reversion
P02, basis futures P06, ML P09) — branchés via ``REAL_PRODUCERS`` sans changer la logique du desk
(OCP). ``DEFAULT_PRODUCERS`` (mocks) reste pour les tests de régression. La série de prix desk est
**explicitement simulée** (rule ``forward-real-simulated``) : aucun alpha n'est revendiqué — un
brut flatteur sur synthétique est un artefact (cf. results/SYNTHESIS.md). On valide le PIPELINE
(pondération sous risque + coûts d'exécution → PnL net) sur de vrais signaux.

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
from typing import Callable

import mlflow
import numpy as np
import pandas as pd

from core.backtest import BacktestEngine, LinearCostModel, cumulative_pnl
from core.backtest.metrics import DefaultMetrics
from core.backtest.protocols import FloatArray, Ledger
from core.backtest.tracking import dvc_version, log_pnl_figure, tracked_run
from core.models.pipeline import FeaturePipeline, SpreadFeatureSpec, build_labels
from core.models.protocols import Model
from core.models.validation import PurgedKFold, oos_predict
from core.models.xgboost_model import SeedBaggingEnsemble, XGBoostDirectionModel
from core.signals import (
    FuturesBasisSignal,
    MeanReversionSignal,
    MLEnsembleSignal,
    SignalProducer,
)

_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE))
from desk import DeskStrategy  # noqa: E402  (src ajouté au sys.path ci-dessus)
from execution import ExecutionModel  # noqa: E402
from portfolio import PortfolioConstructor  # noqa: E402
from provenance import SignalProvenance  # noqa: E402
from signals import ConstantMock, MeanReversionMock, MomentumMock  # noqa: E402

RESULTS_DIR = _HERE.parent / "results"
EXPERIMENT = "p10_portfolio_execution"
SEED = 42
PERIODS_PER_YEAR = 252.0  # desk à pas journalier (démo)
CAPITAL = 1.0

# Paramètres desk fixés *a priori* (non optimisés) → n_trials = 1 (anti multiple-testing).
VOL_LOOKBACK, VOL_FLOOR, GROSS_CAP = 60, 1e-4, 1.0
FEES_BPS, SLIPPAGE_BPS, IMPACT_KAPPA = 10.0, 5.0, 0.02
KAPPA_GRID = [0.0, 0.01, 0.02, 0.05, 0.1]

# Paramètres des VRAIS signaux (fixés *a priori*, cohérents avec P02/P06/P09).
MR_Z_ENTRY, MR_Z_EXIT, MR_LOOKBACK = 2.0, 0.5, 20  # P02 : z-score à hystérésis
BASIS_TAU, BASIS_LOOKBACK = 0.25, 20  # P06 : maturité (années) + fenêtre du carry momentum
ML_HORIZON, ML_N_SPLITS, ML_NEUTRAL_BAND, ML_N_MEMBERS = 5, 5, 0.05, 3  # P09 : OOS purged-CV


def DEFAULT_PRODUCERS() -> list[SignalProducer]:
    """Trois signaux mockés disjoints (carry, mean-reversion, momentum) — placeholders P02/P06/P09."""
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
    """Vecteur de probabilités ``P(montée)`` hors-échantillon de P09, aligné sur ``prices``.

    Reproduit fidèlement le pipeline P09 : features causales dérivées de la série (lags, moyennes
    glissantes, momentums) + cible directionnelle, puis ``oos_predict`` (purged-CV + embargo) avec
    le modèle injecté. Les lignes non prédictibles (warm-up des features, queue sans futur) restent
    ``NaN`` → l'adaptateur P09 les neutralise en position plate. Honnêteté : la proba est OOS
    (anti-overfit) mais **non strictement walk-forward causale** — design assumé de P09.
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
        return proba  # pas assez d'échantillons valides → tout plat (honnête)
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
    """Les 3 **vrais** producteurs promus dans ``core.signals`` : P02, P06, P09.

    - ``MeanReversionSignal`` (P02) : retour à la moyenne du spread (z-score à hystérésis).
    - ``FuturesBasisSignal`` (P06) : carry/roll momentum de la base future↔spot (cost-of-carry).
    - ``MLEnsembleSignal`` (P09) : signal directionnel ML hors-échantillon (ensemble seed-bagging).

    Au PoC, la série desk est synthétique ⇒ tous les signaux restent étiquetés ``simulated=True``.
    ``ml_make_model`` permet d'injecter un modèle léger en test ; par défaut, ensemble XGBoost.
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
        "signal_source": "real (P02/P06/P09 via core.signals)",
        "data_source": "synthetic_desk",
        "simulated": True,
    }


def main() -> None:
    prices, provenance = build_synthetic_prices(n=1500, seed=SEED)
    producers = REAL_PRODUCERS(prices, seed=SEED)  # P02/P06/P09 réels (mocks → réels)
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
