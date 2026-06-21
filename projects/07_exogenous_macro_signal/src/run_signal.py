"""Bout-en-bout P07 : features exogènes point-in-time → lead sur le spread → MLflow.

    uv run python projects/07_exogenous_macro_signal/src/run_signal.py

1. charge le panel exogène (synthétique déterministe à défaut de token) ;
2. construit le panel de features **point-in-time** (`core.features`) ;
3. mesure le lead sur le spread P01 : cross-corrélation aux lags + OLS de confirmation ;
4. versionne le brut exogène (DVC, best-effort) ;
5. logge un run MLflow (variables, lags de publication, fenêtres + SHA + DVC) ;
6. écrit `results/run_summary.json` + `results/SYNTHESIS.md`.
"""

from __future__ import annotations

import json
import subprocess
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
import analysis  # noqa: E402  (src ajouté au sys.path ci-dessus)
import sources  # noqa: E402

logger = get_logger(__name__)

RESULTS_DIR = _HERE.parent / "results"
RAW_EXO_DIR = RAW_DIR / "exogenous"
EXPERIMENT = "p07_exogenous_macro_signal"
MAX_LAG = 7

#: Features dérivées par variable (toutes ≤ t par construction).
FEATURE_SPECS: dict[str, FeatureSpec] = {
    "gas_price": FeatureSpec(lags=(0, 1), rolling_means=(7,), diffs=(7,)),
    "hdd": FeatureSpec(lags=(0,), rolling_means=(7,)),
    "cdd": FeatureSpec(lags=(0,), rolling_means=(7,)),
}


def measure_lead(panel_features: pd.DataFrame, spread: pd.Series) -> dict[str, Any]:
    """Cross-corrélation par feature + OLS de confirmation sur le meilleur lead.

    Mesure sur les **variations** (Δ) et non les niveaux : les séries macro dérivent
    ensemble (saisonnalité, marche aléatoire) et une corrélation de niveaux culmine
    spurieusement à lag 0 (régression fallacieuse, cf. §10). Différencier isole la
    dynamique de lead.
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


def _version_raw(frames: dict[str, pd.DataFrame]) -> dict[str, str]:
    """Écrit le brut exogène et tente `dvc add` (dégrade proprement si bloqué)."""
    RAW_EXO_DIR.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, frame in frames.items():
        path = RAW_EXO_DIR / f"{name}.parquet"
        frame.to_parquet(path)
        paths.append(str(path))
    try:
        subprocess.run(["dvc", "add", *paths], check=True, capture_output=True, text=True)
        pointer = f"{paths[0]}.dvc"
        ignored = (
            subprocess.run(["git", "check-ignore", pointer], capture_output=True).returncode == 0
        )
        # P01 §3 : le motif `data/raw/*` avale aussi les pointeurs .dvc → committal bloqué.
        return {"status": "tracked", "pointer_committable": not ignored}
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        logger.warning("dvc add indisponible/bloqué → brut laissé untracked (%s).", exc)
        return {"status": "untracked", "pointer_committable": False}


def main() -> None:
    panel = sources.load_panel()
    builder = PointInTimeFeatureBuilder(panel.source, FEATURE_SPECS)
    features = builder.build_panel(panel.decision_index)
    spread = panel.spread.reindex(panel.spread.index)  # cible alignée par timestamp

    lead = measure_lead(features, spread)
    dvc_status = _version_raw(panel.raw)

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
        "simulated": True,  # rule forward-real-simulated : données synthétiques étiquetées
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
        "dvc": dvc_status,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    _write_synthesis(summary)

    logger.info(
        "run_id=%s  best=%s lead=%d j |corr|=%.3f  r2_oos=%.3f  dvc=%s",
        run_id,
        lead["best_feature"],
        lead["best_lag"],
        lead["best_abs_corr"],
        lead["ols_confirmation"]["r2_oos"],
        dvc_status["status"],
    )


def _write_synthesis(summary: dict[str, Any]) -> None:
    lead = summary["lead"]
    ols = lead["ols_confirmation"]
    lines = [
        "# P07 — Synthèse : signal macro exogène (lead sur le spread)",
        "",
        "> Données **SIMULÉES** (repli déterministe, seed fixe) : démonstration de",
        "> méthode point-in-time, pas une prétention de réalisme. Connecteur réel",
        "> météo/gaz = item `data-engineer` (cf. CONVERGENCE).",
        "",
        "## Lead observé",
        f"- Meilleure feature : **{lead['best_feature']}**",
        f"- Lead optimal : **{lead['best_lag']} jour(s)** "
        f"(le DGP injecte un lead de {summary['params']['lead_injected_days']} j).",
        f"- |corrélation| au lead : **{lead['best_abs_corr']:.3f}**",
        "",
        "## Confirmation OLS (split temporel strict, pas de shuffle)",
        f"- coef = {ols['coef']:.4f}, p-value = {ols['pvalue']:.2e}",
        f"- R² in-sample = {ols['r2_in']:.3f}, **R² out-of-sample = {ols['r2_oos']:.3f}**",
        f"- n_train = {ols['n_train']}, n_test = {ols['n_test']}",
        "",
        "## Pièges look-ahead couverts",
        "- Lag de publication explicite (knowledge_ts = value_ts + lag) — test rouge.",
        "- Révisions tardives : seul le millésime publié à temps est vu (vintages).",
        "- Alignement / fuseau UTC tz-aware (rejet du datetime naïf).",
        "- Mesure du lead anti-overfit : cross-corrélation + OLS out-of-sample.",
        "",
        f"Run MLflow : `{summary['run_id']}` — brut exogène DVC : {summary['dvc']['status']}"
        + (
            "."
            if summary["dvc"].get("pointer_committable")
            else " (cache local ; pointeurs `.dvc` gitignorés → committal en convergence, "
            "cf. CONVERGENCE)."
        ),
    ]
    (RESULTS_DIR / "SYNTHESIS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
