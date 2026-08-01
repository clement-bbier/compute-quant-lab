"""P07 end-to-end: point-in-time exogenous features -> lead over the spread -> MLflow.

    uv run python projects/07_exogenous_macro_signal/src/run_signal.py

1. loads the exogenous panel (deterministic synthetic fallback absent a token);
2. builds the **point-in-time** feature panel (`core.features`);
3. measures the lead over the P01 spread: cross-correlation across lags + confirmation OLS;
4. writes the raw exogenous data to the local cache (`data/raw/`, gitignored by design);
5. logs an MLflow run (variables, publication lags, windows + git SHA);
6. writes `results/run_summary.json` + `results/SYNTHESIS.md`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import mlflow
import pandas as pd

from core.features import FeatureSpec, PointInTimeFeatureBuilder
from core.utils.config import RAW_DIR
from core.utils.logging import get_logger
from core.utils.tracking import run as tracked_run

_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE))
import analysis  # noqa: E402  (src added to sys.path above)
import sources  # noqa: E402

logger = get_logger(__name__)

RESULTS_DIR = _HERE.parent / "results"
RAW_EXO_DIR = RAW_DIR / "exogenous"
EXPERIMENT = "p07_exogenous_macro_signal"
MAX_LAG = 7

#: Derived features per variable (all <= t by construction).
FEATURE_SPECS: dict[str, FeatureSpec] = {
    "gas_price": FeatureSpec(lags=(0, 1), rolling_means=(7,), diffs=(7,)),
    "hdd": FeatureSpec(lags=(0,), rolling_means=(7,)),
    "cdd": FeatureSpec(lags=(0,), rolling_means=(7,)),
}


def measure_lead(panel_features: pd.DataFrame, spread: pd.Series) -> dict[str, Any]:
    """Per-feature cross-correlation + confirmation OLS on the best lead.

    Measured on **changes** (delta), not levels: macro series drift together
    (seasonality, random walk), and a level correlation peaks spuriously at lag 0
    (spurious regression, cf. §10). Differencing isolates the lead dynamics.
    """
    feature_changes = panel_features.diff()
    spread_changes = spread.diff()

    per_feature: dict[str, dict[str, float]] = {}
    for col in feature_changes.columns:
        corr = analysis.cross_correlations(feature_changes[col].dropna(), spread_changes, MAX_LAG)
        k = analysis.best_lag(corr)
        per_feature[col] = {"best_lag": int(k), "corr": float(corr.loc[k])}

    best_feature = max(per_feature, key=lambda c: abs(per_feature[c]["corr"]))
    best = per_feature[best_feature]
    ols = analysis.confirm_ols(
        feature_changes[best_feature].dropna(), spread_changes, lag=best["best_lag"]
    )
    return {
        "best_feature": best_feature,
        "best_lag": best["best_lag"],
        "best_abs_corr": abs(best["corr"]),
        "per_feature": per_feature,
        "ols_confirmation": ols,
    }


def _write_raw(frames: dict[str, pd.DataFrame]) -> dict[str, str]:
    """Writes the raw exogenous data to the local cache (`data/raw/`, gitignored by design)."""
    RAW_EXO_DIR.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, frame in frames.items():
        path = RAW_EXO_DIR / f"{name}.parquet"
        frame.to_parquet(path)
        paths.append(str(path))
    return {"status": "local_cache", "paths": ",".join(paths)}


def main() -> None:
    panel = sources.load_panel()
    builder = PointInTimeFeatureBuilder(panel.source, FEATURE_SPECS)
    features = builder.build_panel(panel.decision_index)
    spread = panel.spread.reindex(panel.spread.index)  # target aligned by timestamp

    lead = measure_lead(features, spread)
    raw_status = _write_raw(panel.raw)

    lags_days = {k: v / pd.Timedelta("1D") for k, v in sources.DEFAULT_PUBLICATION_LAGS.items()}
    params = {
        "mode": panel.mode,
        "seed": sources.DEMO_SEED,
        "lead_injected_days": sources.LEAD_DAYS,
        "variables": ",".join(panel.source.names()),
        "publication_lags_days": json.dumps(lags_days),
        "feature_specs": json.dumps({k: v.__dict__ for k, v in FEATURE_SPECS.items()}),
        "max_lag": MAX_LAG,
        "n_decision_points": int(len(features)),
        "simulated": True,  # rule forward-real-simulated: synthetic data flagged as such
    }

    with tracked_run(EXPERIMENT, params):
        mlflow.log_metric("best_abs_corr", lead["best_abs_corr"])
        mlflow.log_metric("best_lag", lead["best_lag"])
        mlflow.log_metric("ols_r2_oos", lead["ols_confirmation"]["r2_oos"])
        mlflow.log_metric("ols_coef", lead["ols_confirmation"]["coef"])
        mlflow.log_metric("ols_pvalue", lead["ols_confirmation"]["pvalue"])
        mlflow.log_dict(lead["per_feature"], "cross_correlations.json")
        run_id = mlflow.active_run().info.run_id

    summary = {
        "run_id": run_id,
        "params": params,
        "lead": {k: v for k, v in lead.items() if k != "per_feature"},
        "per_feature": lead["per_feature"],
        "raw_data": raw_status,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    _write_synthesis(summary)

    logger.info(
        "run_id=%s  best=%s lead=%dd |corr|=%.3f  r2_oos=%.3f  raw=%s",
        run_id,
        lead["best_feature"],
        lead["best_lag"],
        lead["best_abs_corr"],
        lead["ols_confirmation"]["r2_oos"],
        raw_status["status"],
    )


def _write_synthesis(summary: dict[str, Any]) -> None:
    lead = summary["lead"]
    ols = lead["ols_confirmation"]
    lines = [
        "# P07 — Synthesis: exogenous macro signal (lead over the spread)",
        "",
        "> **SIMULATED** data (deterministic fallback, fixed seed): a demonstration of",
        "> point-in-time method, not a claim of realism. A real weather/gas",
        "> connector remains a `data-engineer` backlog item.",
        "",
        "## Observed lead",
        f"- Best feature: **{lead['best_feature']}**",
        f"- Optimal lead: **{lead['best_lag']} day(s)** "
        f"(the DGP injects a {summary['params']['lead_injected_days']}-day lead).",
        f"- |correlation| at lead: **{lead['best_abs_corr']:.3f}**",
        "",
        "## OLS confirmation (strict temporal split, no shuffling)",
        f"- coef = {ols['coef']:.4f}, p-value = {ols['pvalue']:.2e}",
        f"- in-sample R² = {ols['r2_in']:.3f}, **out-of-sample R² = {ols['r2_oos']:.3f}**",
        f"- n_train = {ols['n_train']}, n_test = {ols['n_test']}",
        "",
        "## Look-ahead pitfalls covered",
        "- Explicit publication lag (knowledge_ts = value_ts + lag) — red-first test.",
        "- Late revisions: only the vintage published in time is seen (vintages).",
        "- UTC tz-aware alignment (naive datetime rejected).",
        "- Anti-overfit lead measurement: cross-correlation + out-of-sample OLS.",
        "",
        f"MLflow run: `{summary['run_id']}` — raw exogenous data: "
        f"{summary['raw_data']['status']} (data/raw/, gitignored by design).",
    ]
    (RESULTS_DIR / "SYNTHESIS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
