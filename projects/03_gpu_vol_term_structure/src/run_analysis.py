"""Entrée exécutable P03 : vol réalisée/EWMA + term structure de la forward SIMULÉE.

Usage :
    uv run python projects/03_gpu_vol_term_structure/src/run_analysis.py

Pipeline (modèle d'honnêteté de P01/P04) :
1. série spot via l'indice sur snapshots réels (``data/snapshots/``) si présents, sinon
   **historique synthétique déterministe étiqueté démo** (seed fixe) ;
2. volatilité **réalisée** + **EWMA** sur les log-returns → régime de vol courant ;
3. courbe forward **SIMULÉE** de P04 (Schwartz 1-facteur) calibrée sur le log-spot ;
4. **term structure** (pente/courbure/forme) + **signal** directionnel (roll-yield) ;
5. **run MLflow** loggué (params + métriques + SHA git + DVC) ;
6. synthèse écrite dans ``results/`` (``SYNTHESIS.md`` + ``run_summary.json``).

⚠️ La term structure dérive d'une forward **SIMULÉE** (futures CME non listés) : tout
résultat est conditionnel au modèle, jamais présenté comme observé.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import math
import os
import sys
from pathlib import Path

import numpy as np

# Convention labo : tracking MLflow fichier local (opt-in requis par MLflow 2026).
os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")
_ROOT = Path(__file__).resolve().parents[3]
os.environ.setdefault("MLFLOW_TRACKING_URI", (_ROOT / "experiments" / "mlruns").as_uri())

# Rend importables : les modules P03 (ce dossier) et le paquet `forward` de P04 (lecture).
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(_ROOT / "projects" / "04_compute_index_curve" / "src"))

import mlflow  # noqa: E402

from core.ingestion import CsvSnapshotStore  # noqa: E402
from core.utils import tracking  # noqa: E402
from forward.build_curve import build_forward_curve  # noqa: E402

from signals import directional_signal  # noqa: E402
from spot_series import build_spot_series  # noqa: E402
from term_structure import TermStructureAnalyzer  # noqa: E402
from vol import EwmaVol, RealizedVol, log_returns  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("run_analysis")

SNAPSHOT_DIR = _ROOT / "data" / "snapshots"
RESULTS_DIR = Path(__file__).resolve().parents[1] / "results"
GPU_MODEL = "H100"
MATURITIES = [0.0, 7.0, 30.0, 90.0, 180.0, 360.0]
VOL_WINDOW = 20
LAMBDA_EWMA = 0.94
PERIODS_PER_YEAR = 365.0
SEED = 7
MIN_SERIES_POINTS = VOL_WINDOW + 5  # assez de points pour une vol réalisée non triviale


def _last_finite(series: np.ndarray) -> float:
    """Dernière valeur finie d'une série (vol courante), NaN si aucune."""
    finite = series[np.isfinite(series)]
    return float(finite[-1]) if finite.size else float("nan")


def _demo_prices(n: int = 180, spot: float = 2.30) -> np.ndarray:
    """Série de prix spot synthétique mean-reverting (placeholder étiqueté démo)."""
    rng = np.random.default_rng(SEED)
    kappa, sigma, dt_days = 0.05, 0.06, 1.0
    ln_theta = math.log(spot)
    decay = math.exp(-kappa * dt_days)
    sd = math.sqrt((sigma**2 / (2 * kappa)) * (1 - math.exp(-2 * kappa * dt_days)))
    x = np.empty(n)
    x[0] = ln_theta
    for t in range(1, n):
        x[t] = decay * x[t - 1] + (1 - decay) * ln_theta + sd * rng.standard_normal()
    return np.exp(x)


def _daily_grid(snaps: list) -> list[dt.datetime]:
    """Grille quotidienne de fix (00:30 UTC) couvrant l'amplitude des snapshots."""
    days = sorted({s.snapshotted_at.date() for s in snaps})
    return [dt.datetime(d.year, d.month, d.day, 0, 30, tzinfo=dt.timezone.utc) for d in days]


def _spot_prices() -> tuple[np.ndarray, bool]:
    """Série spot réelle (snapshots) si exploitable, sinon repli synthétique démo."""
    snaps = CsvSnapshotStore(SNAPSHOT_DIR).load() if SNAPSHOT_DIR.exists() else []
    if snaps:
        _, prices = build_spot_series(snaps, _daily_grid(snaps), GPU_MODEL)
        if prices.size >= MIN_SERIES_POINTS:
            logger.info("Série spot RÉELLE de l'indice : %d points.", prices.size)
            return prices, True
        logger.warning("Snapshots présents mais série trop courte : repli synthétique démo.")
    return _demo_prices(), False


def main() -> None:
    prices, real_spot = _spot_prices()
    rets = log_returns(prices)

    realized = RealizedVol(window=VOL_WINDOW, periods_per_year=PERIODS_PER_YEAR).estimate(rets)
    ewma = EwmaVol(lam=LAMBDA_EWMA, periods_per_year=PERIODS_PER_YEAR).estimate(rets)
    rv_current, ev_current = _last_finite(realized), _last_finite(ewma)

    spot = float(prices[-1])
    log_history = list(np.log(prices))

    # Forward SIMULÉE de P04 (logue son propre run MLflow ; appelée hors de notre run).
    curve = build_forward_curve(log_history, spot=spot, maturities_days=MATURITIES)

    as_of = dt.datetime.now(dt.timezone.utc)
    ts = TermStructureAnalyzer().analyze(
        np.asarray(curve.maturities),
        np.asarray(curve.prices),
        simulated=curve.simulated,
        as_of=as_of,
    )
    sig = directional_signal(ts)

    params = {
        "gpu_model": GPU_MODEL,
        "vol_window": VOL_WINDOW,
        "lambda_ewma": LAMBDA_EWMA,
        "periods_per_year": PERIODS_PER_YEAR,
        "seed": SEED,
        "spot_source": "real_index" if real_spot else "synthetic_demo",
        "forward_simulated": ts.simulated,  # toujours True : frontière réel/simulé
        "curve_model": curve.model_name,
    }
    with tracking.run("gpu_vol_term_structure", params):
        mlflow.log_metric("realized_vol_current", rv_current)
        mlflow.log_metric("ewma_vol_current", ev_current)
        mlflow.log_metric("spot", spot)
        mlflow.log_metric("ts_slope", ts.slope)
        mlflow.log_metric("ts_curvature", ts.curvature)
        mlflow.log_metric("signal", sig.value)
        active = mlflow.active_run()
        run_id = active.info.run_id if active is not None else "unknown"

    summary = {
        "as_of": as_of.isoformat(),
        "gpu_model": GPU_MODEL,
        "spot_source": params["spot_source"],
        "spot_usd_per_gpu_h": spot,
        "realized_vol_annualized": rv_current,
        "ewma_vol_annualized": ev_current,
        "term_structure": {
            "shape": ts.shape,
            "slope": ts.slope,
            "curvature": ts.curvature,
            "front_price": ts.front_price,
            "simulated": ts.simulated,
        },
        "signal": {"value": sig.value, "rationale": sig.rationale, "simulated": sig.simulated},
        "mlflow_run_id": run_id,
        "curve_model": curve.model_name,
    }
    _write_results(summary)

    logger.info(
        "Vol réalisée %.1f%% | EWMA %.1f%% (annualisées).", rv_current * 100, ev_current * 100
    )
    logger.info(
        "Term structure SIMULÉE : %s (pente=%.4g) -> signal=%+d.", ts.shape, ts.slope, sig.value
    )
    logger.info("Run MLflow %s loggué ; synthèse écrite dans %s.", run_id, RESULTS_DIR)


def _write_results(summary: dict) -> None:
    """Écrit ``run_summary.json`` + ``SYNTHESIS.md`` dans ``results/``."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    ts = summary["term_structure"]
    note_real = (
        "indice spot **réel**"
        if summary["spot_source"] == "real_index"
        else "spot **synthétique de démo** (seed fixe)"
    )
    md = f"""# P03 — Synthèse vol & term structure

> Run de démonstration. Reproductible : `src/run_analysis.py` (MLflow). Chiffres bruts :
> [`run_summary.json`](run_summary.json). MLflow run `{summary["mlflow_run_id"]}`.

## 1. Couverture du run

| Élément | Valeur |
|---|---|
| GPU / fix | {summary["gpu_model"]} |
| Jambe spot | {note_real}, {summary["spot_usd_per_gpu_h"]:.4f} $/GPU·h |
| Jambe forward | **SIMULÉE** (Schwartz 1-facteur, modèle `{summary["curve_model"]}`) |

**Note d'honnêteté** : l'historique compute est court (snapshots récents). Tant que la
série réelle est mince, le run tourne sur un spot synthétique étiqueté démo ; il bascule
sur l'indice réel dès que `data/snapshots/` est assez profond, sans autre changement.

## 2. Volatilité (annualisée)

| Estimateur | Vol |
|---|---|
| Réalisée (fenêtre {VOL_WINDOW}) | **{summary["realized_vol_annualized"] * 100:.1f} %** |
| EWMA (λ={LAMBDA_EWMA}) | **{summary["ewma_vol_annualized"] * 100:.1f} %** |

## 3. Structure par terme (SIMULÉE) & signal

| Descripteur | Valeur |
|---|---|
| Forme | **{ts["shape"]}** |
| Pente ($/GPU·h/j) | {ts["slope"]:.4g} |
| Courbure (butterfly) | {ts["curvature"]:.4g} |
| Signal directionnel | **{summary["signal"]["value"]:+d}** ({summary["signal"]["rationale"]}) |

> ⚠️ **Frontière réel/simulé** : la term structure et le signal dérivent d'une courbe
> forward **simulée** (`simulated={ts["simulated"]}`). Conditionnels au modèle, jamais
> servis comme un prix de marché observé.

## 4. Limites

- Historique compute court → vol et calibration peu robustes (intervalle large).
- Forward simulée → la forme de la courbe reflète le modèle (mean-reversion Schwartz),
  pas une anticipation de marché observée.
- Signal roll-yield = convention (backwardation→long) : à valider sur données réelles
  une fois les futures compute listés / la série spot accumulée.
"""
    (RESULTS_DIR / "SYNTHESIS.md").write_text(md, encoding="utf-8")


if __name__ == "__main__":
    main()
