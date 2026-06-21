"""Run headline P09 : features point-in-time → purged-CV OOS → ensemble → backtest P08.

Pipeline reproductible et HONNÊTE sur données **simulées** (provenance ``simulated=True``) :

1. features point-in-time (spread P01 + exogènes P07 lagués) et cible directionnelle ;
2. prédictions **hors-échantillon** par purged k-fold + embargo (jamais de shuffle), avec un
   ensemble de graines XGBoost (réduction de variance) ;
3. signal OOS → `PrecomputedSignalStrategy` → moteur de backtest P08 ;
4. métriques de risque + **Sharpe dégonflé** (Probabilistic Sharpe Ratio, tenant compte du
   nombre d'essais, de la taille d'échantillon et de la non-normalité) ;
5. run MLflow (params + n_trials + seed + fenêtres + SHA + DVC + figure PnL).

    uv run python projects/09_ml_signal_ensemble/src/run_train.py

⚠️ Le Sharpe sur synthétique n'est PAS un alpha : voir results/SYNTHESIS.md (verdict adversarial).
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
from core.backtest.tracking import dvc_version, log_metrics, log_pnl_figure, tracked_run
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

_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE))
from synthetic import SyntheticDataset, generate  # noqa: E402  (src ajouté au sys.path)

RESULTS_DIR = _HERE.parent / "results"
EXPERIMENT = "p09_ml_signal_ensemble"
SEED = 42
PERIODS_PER_YEAR = 365.0  # grille journalière

# --- Hyperparamètres fixés *a priori* (AUCUNE recherche) → n_trials = 1 -------------------
HORIZON = 1  # on prédit la direction du spread au pas suivant
N_SPLITS, EMBARGO = 5, 5
NEUTRAL_BAND = 0.05  # politique proba→position choisie par le directeur de recherche
ENSEMBLE_SEEDS = (11, 22, 33)
N_ESTIMATORS, MAX_DEPTH, LEARNING_RATE = 150, 3, 0.05
FEES_BPS, SLIPPAGE_BPS = 10.0, 5.0
N_TRIALS = 1  # config figée a priori : pas de multiple-testing (à incrémenter si on tune)

# Features dérivées du spread (causales) et des exogènes P07 (point-in-time, lag de publication).
_SPREAD_SPEC = SpreadFeatureSpec(lags=(1, 2, 3), rolling_means=(5, 10), momentums=(3, 5))
_EXOG_SPECS = {
    "gas_price": FeatureSpec(lags=(0, 1), rolling_means=(5,), diffs=(1,)),
    "hdd": FeatureSpec(lags=(0,), rolling_means=(5,)),
}


def build_features(dataset: SyntheticDataset) -> tuple[pd.DataFrame, pd.Series]:
    """Matrice de features point-in-time (spread + exogènes P07) et cible directionnelle."""
    exog_builder = PointInTimeFeatureBuilder(source=dataset.exog_source, specs=_EXOG_SPECS)
    pipeline = FeaturePipeline(spread_spec=_SPREAD_SPEC, exog_builder=exog_builder)
    features = pipeline.build_matrix(dataset.spread)
    labels = build_labels(dataset.spread, horizon=HORIZON)
    return features, labels


def _make_ensemble() -> SeedBaggingEnsemble:
    """Fabrique un ensemble neuf (appelé par fold dans `oos_predict`)."""
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
    """Vecteur de probabilités OOS aligné sur l'index complet (NaN hors zone prédictible).

    On ne conserve que les lignes à features ET label valides (warm-up et queue exclus),
    on prédit ces lignes en purged-CV, puis on ré-aligne sur la série complète.
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
    """Probabilistic / Deflated Sharpe Ratio à partir de la série de rendements par période."""
    std = float(returns.std(ddof=1))
    if std == 0.0:
        return 0.0
    sr_per_period = float(returns.mean()) / std
    return deflated_sharpe_ratio(
        sr_per_period,
        n_obs=returns.size,
        n_trials=n_trials,
        sr_variance=1.0,  # inutilisé à n_trials=1 (max attendu = 0) ; explicite pour la suite
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
        "dvc_version": dvc_version(),
        "params": params,
        "metrics": metrics,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "last_run.json").write_text(
        json.dumps(snapshot, indent=2, default=str), encoding="utf-8"
    )

    print(
        f"run_id={run_id}  simulated={dataset.provenance.simulated}  source={dataset.provenance.source}"
    )
    print(
        f"obs={params['n_obs']}  predicted={n_predicted}  features={params['n_features']}  n_trials={N_TRIALS}"
    )
    for name, value in metrics.items():
        print(f"  {name:22s} = {value:.6f}")
    print(
        "\n[!] Sharpe sur SIMULE - non credible comme alpha. Le Sharpe degonfle (PSR) et le "
        "verdict adversarial (results/SYNTHESIS.md) priment."
    )


if __name__ == "__main__":
    main()
