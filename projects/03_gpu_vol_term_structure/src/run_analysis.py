"""Executable entry point for P03: realized/EWMA vol + term structure of the SIMULATED forward.

Usage:
    uv run python projects/03_gpu_vol_term_structure/src/run_analysis.py

Pipeline (honesty model shared with P01/P04):
1. spot series via the index on real snapshots (``data/snapshots/``) if present, else
   **deterministic synthetic history labeled demo** (fixed seed);
2. **realized** + **EWMA** volatility on log-returns → current vol regime;
3. **SIMULATED** forward curve from P04 (1-factor Schwartz) calibrated on the log-spot;
4. **term structure** (slope/curvature/shape) + directional (roll-yield) **signal**;
5. logged **MLflow run** (params + metrics + git SHA);
6. synthesis written to ``results/`` (``SYNTHESIS.md`` + ``run_summary.json``).

Warning: the term structure derives from a **SIMULATED** forward (CME futures not listed): any
result is conditional on the model, never presented as observed.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import os
import sys
from pathlib import Path

import numpy as np

# Lab convention: local file-based MLflow tracking (opt-in required by MLflow 2026).
os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")
_ROOT = Path(__file__).resolve().parents[3]
os.environ.setdefault("MLFLOW_TRACKING_URI", (_ROOT / "experiments" / "mlruns").as_uri())

# Makes importable: the P03 modules (this folder) and the P04 `forward` package (read-only).
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(_ROOT / "projects" / "04_compute_index_curve" / "src"))

import mlflow  # noqa: E402

from core.ingestion import CsvSnapshotStore  # noqa: E402
from core.utils import tracking  # noqa: E402
from core.utils.logging import configure_logging, get_logger  # noqa: E402
from forward.build_curve import build_forward_curve  # noqa: E402

from signals import directional_signal  # noqa: E402
from spot_series import build_spot_series  # noqa: E402
from term_structure import TermStructureAnalyzer  # noqa: E402
from vol import EwmaVol, RealizedVol, log_returns  # noqa: E402

logger = get_logger("run_analysis")

SNAPSHOT_DIR = _ROOT / "data" / "snapshots"
RESULTS_DIR = Path(__file__).resolve().parents[1] / "results"
GPU_MODEL = "H100"
MATURITIES = [0.0, 7.0, 30.0, 90.0, 180.0, 360.0]
VOL_WINDOW = 20
LAMBDA_EWMA = 0.94
PERIODS_PER_YEAR = 365.0
SEED = 7
MIN_SERIES_POINTS = VOL_WINDOW + 5  # enough points for a non-trivial realized vol


def _last_finite(series: np.ndarray) -> float:
    """Last finite value of a series (current vol), NaN if none."""
    finite = series[np.isfinite(series)]
    return float(finite[-1]) if finite.size else float("nan")


def _demo_prices(n: int = 180, spot: float = 2.30) -> np.ndarray:
    """Synthetic mean-reverting spot price series (demo-labeled placeholder)."""
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
    """Daily fix grid (00:30 UTC) covering the span of the snapshots."""
    days = sorted({s.snapshotted_at.date() for s in snaps})
    return [dt.datetime(d.year, d.month, d.day, 0, 30, tzinfo=dt.timezone.utc) for d in days]


def _spot_prices() -> tuple[np.ndarray, bool]:
    """Real spot series (snapshots) if usable, else demo synthetic fallback."""
    snaps = CsvSnapshotStore(SNAPSHOT_DIR).load() if SNAPSHOT_DIR.exists() else []
    if snaps:
        _, prices = build_spot_series(snaps, _daily_grid(snaps), GPU_MODEL)
        if prices.size >= MIN_SERIES_POINTS:
            logger.info("REAL index spot series: %d points.", prices.size)
            return prices, True
        logger.warning("Snapshots present but series too short: falling back to demo synthetic.")
    return _demo_prices(), False


def main() -> None:
    prices, real_spot = _spot_prices()
    rets = log_returns(prices)

    realized = RealizedVol(window=VOL_WINDOW, periods_per_year=PERIODS_PER_YEAR).estimate(rets)
    ewma = EwmaVol(lam=LAMBDA_EWMA, periods_per_year=PERIODS_PER_YEAR).estimate(rets)
    rv_current, ev_current = _last_finite(realized), _last_finite(ewma)

    spot = float(prices[-1])
    log_history = list(np.log(prices))

    # SIMULATED forward from P04 (logs its own MLflow run; called outside our run).
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
        "forward_simulated": ts.simulated,  # always True: real/simulated boundary
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
        "Realized vol %.1f%% | EWMA %.1f%% (annualized).", rv_current * 100, ev_current * 100
    )
    logger.info(
        "SIMULATED term structure: %s (slope=%.4g) -> signal=%+d.", ts.shape, ts.slope, sig.value
    )
    logger.info("MLflow run %s logged; synthesis written to %s.", run_id, RESULTS_DIR)


def _write_results(summary: dict) -> None:
    """Writes ``run_summary.json`` + ``SYNTHESIS.md`` to ``results/``."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    ts = summary["term_structure"]
    note_real = (
        "**real** spot index"
        if summary["spot_source"] == "real_index"
        else "**demo synthetic** spot (fixed seed)"
    )
    md = f"""# P03 — Vol & term structure synthesis

> Demonstration run. Reproducible: `src/run_analysis.py` (MLflow). Raw figures:
> [`run_summary.json`](run_summary.json). MLflow run `{summary["mlflow_run_id"]}`.

## 1. Run coverage

| Item | Value |
|---|---|
| GPU / fix | {summary["gpu_model"]} |
| Spot leg | {note_real}, {summary["spot_usd_per_gpu_h"]:.4f} $/GPU·h |
| Forward leg | **SIMULATED** (1-factor Schwartz, `{summary["curve_model"]}` model) |

**Honesty note**: the compute history is short (recent snapshots). While the
real series remains thin, the run uses a demo-labeled synthetic spot; it switches
to the real index once `data/snapshots/` is deep enough, with no other change.

## 2. Volatility (annualized)

| Estimator | Vol |
|---|---|
| Realized (window {VOL_WINDOW}) | **{summary["realized_vol_annualized"] * 100:.1f} %** |
| EWMA (λ={LAMBDA_EWMA}) | **{summary["ewma_vol_annualized"] * 100:.1f} %** |

## 3. Term structure (SIMULATED) & signal

| Descriptor | Value |
|---|---|
| Shape | **{ts["shape"]}** |
| Slope ($/GPU·h/day) | {ts["slope"]:.4g} |
| Curvature (butterfly) | {ts["curvature"]:.4g} |
| Directional signal | **{summary["signal"]["value"]:+d}** ({summary["signal"]["rationale"]}) |

> Warning: **Real/simulated boundary**: the term structure and signal derive from a
> **simulated** forward curve (`simulated={ts["simulated"]}`). Conditional on the model, never
> served as an observed market price.

## 4. Limitations

- Short compute history → vol and calibration not very robust (wide interval).
- Simulated forward → the curve's shape reflects the model (Schwartz mean-reversion),
  not an observed market anticipation.
- Roll-yield signal = convention (backwardation→long): to be validated on real data
  once compute futures are listed / the spot series has accumulated.
"""
    (RESULTS_DIR / "SYNTHESIS.md").write_text(md, encoding="utf-8")


if __name__ == "__main__":
    configure_logging()
    main()
