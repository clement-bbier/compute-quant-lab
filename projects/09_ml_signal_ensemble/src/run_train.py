"""P09 headline run: point-in-time features → purged-CV OOS → ensemble → P08 backtest.

Reproducible and HONEST pipeline on **simulated** data (provenance ``simulated=True``):

1. point-in-time features (P01 spread + lagged P07 exogenous variables) and directional target;
2. **out-of-sample** predictions via purged k-fold + embargo (never shuffled), with an
   XGBoost seed ensemble (variance reduction);
3. OOS signal → `PrecomputedSignalStrategy` → P08 backtest engine;
4. risk metrics + **deflated Sharpe** (Probabilistic Sharpe Ratio, accounting for the
   number of trials, sample size, and non-normality);
5. MLflow run (params + n_trials + seed + windows + SHA + PnL figure).

    uv run python projects/09_ml_signal_ensemble/src/run_train.py

Warning: the Sharpe on synthetic data is NOT an alpha claim: see results/SYNTHESIS.md
(adversarial verdict).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import mlflow
import numpy as np
import pandas as pd
from scipy.stats import kurtosis as scipy_kurtosis
from scipy.stats import skew as scipy_skew

from core.backtest import BacktestEngine, LinearCostModel, cumulative_pnl
from core.backtest.tracking import log_metrics, log_pnl_figure, tracked_run
from core.features import FeatureSpec, PointInTimeFeatureBuilder
from core.models import (
    FeaturePipeline,
    PrecomputedSignalStrategy,
    PurgedKFold,
    SeedBaggingEnsemble,
    SpreadFeatureSpec,
    XGBoostDirectionModel,
    build_labels,
    deflated_sharpe_ratio,
    oos_predict,
)
from core.utils.logging import configure_logging, get_logger

_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE))
from synthetic import SyntheticDataset, generate  # noqa: E402  (src added to sys.path)

RESULTS_DIR = _HERE.parent / "results"
EXPERIMENT = "p09_ml_signal_ensemble"
log = get_logger("run_train")
SEED = 42
PERIODS_PER_YEAR = 365.0  # daily grid

# --- Hyperparameters fixed *a priori* (NO search) -> n_trials = 1 -------------------------
HORIZON = 1  # predict the spread direction at the next step
N_SPLITS, EMBARGO = 5, 5
NEUTRAL_BAND = 0.05  # proba->position policy chosen by the research lead
ENSEMBLE_SEEDS = (11, 22, 33)
N_ESTIMATORS, MAX_DEPTH, LEARNING_RATE = 150, 3, 0.05
FEES_BPS, SLIPPAGE_BPS = 10.0, 5.0
N_TRIALS = 1  # config fixed a priori: no multiple-testing (increment if tuning)

# Features derived from the spread (causal) and from the P07 exogenous variables (point-in-time, publication lag).
_SPREAD_SPEC = SpreadFeatureSpec(lags=(1, 2, 3), rolling_means=(5, 10), momentums=(3, 5))
_EXOG_SPECS = {
    "gas_price": FeatureSpec(lags=(0, 1), rolling_means=(5,), diffs=(1,)),
    "hdd": FeatureSpec(lags=(0,), rolling_means=(5,)),
}


def build_features(dataset: SyntheticDataset) -> tuple[pd.DataFrame, pd.Series]:
    """Point-in-time feature matrix (spread + P07 exogenous variables) and directional target."""
    exog_builder = PointInTimeFeatureBuilder(source=dataset.exog_source, specs=_EXOG_SPECS)
    pipeline = FeaturePipeline(spread_spec=_SPREAD_SPEC, exog_builder=exog_builder)
    features = pipeline.build_matrix(dataset.spread)
    labels = build_labels(dataset.spread, horizon=HORIZON)
    return features, labels


def _make_ensemble() -> SeedBaggingEnsemble:
    """Build a fresh ensemble (called per fold inside `oos_predict`)."""
    return SeedBaggingEnsemble(
        make_model=lambda seed: XGBoostDirectionModel(
            random_state=seed,
            n_estimators=N_ESTIMATORS,
            max_depth=MAX_DEPTH,
            learning_rate=LEARNING_RATE,
        ),
        seeds=ENSEMBLE_SEEDS,
    )


def out_of_sample_proba(features: pd.DataFrame, labels: pd.Series) -> np.ndarray:
    """OOS probability vector aligned on the full index (NaN outside the predictable zone).

    We keep only rows with both valid features AND a valid label (warm-up and tail
    excluded), predict those rows under purged-CV, then re-align onto the full series.
    """
    valid = features.notna().all(axis=1) & labels.notna()
    x_clean = features[valid].to_numpy(dtype=np.float64)
    y_clean = labels[valid].to_numpy(dtype=np.float64)
    splitter = PurgedKFold(n_splits=N_SPLITS, horizon=HORIZON, embargo=EMBARGO)
    proba_clean = oos_predict(_make_ensemble, x_clean, y_clean, splitter)

    proba_full = np.full(len(features), np.nan, dtype=np.float64)
    proba_full[np.flatnonzero(valid.to_numpy())] = proba_clean
    return proba_full


def probabilistic_sharpe(returns: np.ndarray, *, n_trials: int) -> float:
    """Probabilistic / Deflated Sharpe Ratio from the per-period returns series."""
    std = float(returns.std(ddof=1))
    if std == 0.0:
        return 0.0
    sr_per_period = float(returns.mean()) / std
    return deflated_sharpe_ratio(
        sr_per_period,
        n_obs=returns.size,
        n_trials=n_trials,
        sr_variance=1.0,  # unused at n_trials=1 (expected max = 0); explicit for later
        skew=float(scipy_skew(returns)),
        kurtosis=float(scipy_kurtosis(returns, fisher=False)),
    )


def main() -> None:
    dataset = generate(seed=SEED)
    features, labels = build_features(dataset)
    proba = out_of_sample_proba(features, labels)

    strategy = PrecomputedSignalStrategy(proba, neutral_band=NEUTRAL_BAND)
    engine = BacktestEngine(
        cost_model=LinearCostModel(fees_bps=FEES_BPS, slippage_bps=SLIPPAGE_BPS),
        periods_per_year=PERIODS_PER_YEAR,
    )
    spread = dataset.spread.to_numpy(dtype=np.float64)

    n_predicted = int(np.isfinite(proba).sum())
    params = {
        "strategy": "ml_ensemble_directional",
        "model": "xgboost_seed_bagging",
        "ensemble_seeds": ",".join(map(str, ENSEMBLE_SEEDS)),
        "n_estimators": N_ESTIMATORS,
        "max_depth": MAX_DEPTH,
        "learning_rate": LEARNING_RATE,
        "horizon": HORIZON,
        "n_splits": N_SPLITS,
        "embargo": EMBARGO,
        "neutral_band": NEUTRAL_BAND,
        "fees_bps": FEES_BPS,
        "slippage_bps": SLIPPAGE_BPS,
        "periods_per_year": PERIODS_PER_YEAR,
        "seed": SEED,
        "n_obs": int(spread.shape[0]),
        "n_predicted": n_predicted,
        "n_features": int(features.shape[1]),
        "feature_names": ",".join(features.columns),
        "n_trials": N_TRIALS,
        "data_source": dataset.provenance.source,
        "simulated": dataset.provenance.simulated,
    }
    result = engine.run(spread, strategy, params=params)

    psr = probabilistic_sharpe(result.ledger.returns, n_trials=N_TRIALS)
    metrics = {
        **result.metrics,
        "deflated_sharpe_psr": psr,
        "n_trades": float(result.ledger.n_trades),
    }

    os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")
    mlflow.set_tracking_uri((RESULTS_DIR / "mlruns").as_uri())
    with tracked_run(EXPERIMENT, params):
        log_metrics(metrics)
        log_pnl_figure(cumulative_pnl(result.ledger.pnl))
        mlflow.set_tag("simulated", str(dataset.provenance.simulated))
        run_id = mlflow.active_run().info.run_id

    snapshot = {
        "run_id": run_id,
        "params": params,
        "metrics": metrics,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "last_run.json").write_text(
        json.dumps(snapshot, indent=2, default=str), encoding="utf-8"
    )

    log.info(
        "run_id=%s  simulated=%s  source=%s",
        run_id,
        dataset.provenance.simulated,
        dataset.provenance.source,
    )
    log.info(
        "obs=%d  predicted=%d  features=%d  n_trials=%d",
        params["n_obs"],
        n_predicted,
        params["n_features"],
        N_TRIALS,
    )
    for name, value in metrics.items():
        log.info("  %-22s = %.6f", name, value)
    log.warning(
        "Sharpe on SIMULATED data - not credible as alpha. The deflated Sharpe (PSR) and "
        "the adversarial verdict (results/SYNTHESIS.md) take precedence."
    )


if __name__ == "__main__":
    configure_logging()
    main()
