# P04 — Compute spot index + simulated forward curve

Lab's foundational data product: (1) a **compute spot index** built according to the
standard set by the leading market players, (2) a **SIMULATED forward curve** (Rust
Monte-Carlo) for the announced-but-unlisted CME compute futures. On which P03 (term
structure) and P06 (derivatives) will depend.

## Data sources

| Leg | Real / Simulated | Source | Unit | Status |
|---|---|---|---|---|
| Spot index (PoC) | **Real** | Accumulated Vast.ai/RunPod marketplace snapshots (`data/snapshots/`) | $/GPU·h | wired (token-gated collector) |
| Spot index (canonical) | **Real** | Silicon Data `SDH100RT` (CME futures settlement) | $/GPU·h | `SiliconDataSource` interface documented, to be wired |
| Forward curve | **SIMULATED** | 1-factor Schwartz model seeded on spot | $/GPU·h per maturity | wired (Rust + Python oracle) |

> Warning: **Real/simulated boundary**: every forward curve carries `Curve.simulated = True` (required
> field, no default). Never served as a real price.

## Index methodology (market standard)

Calibrated against **GPU Markets** (public, reproducible) and **Silicon Data** (CME settlement):

- **trimmed mean 20%** estimator + outlier rejection at **2.5 MAD** (`method='trimmed_mean20+mad2.5'`);
- **no carry-forward**, **24h** staleness window (anti-survivorship);
- exclusion of hyperscaler list prices from the estimator; separation by `lease_type`;
- strictly **point-in-time** fix (`snapshotted_at <= as_of`), age of the oldest retained reading tracked.

Everything is **configurable** (Strategy pattern): estimator, outlier filter, window,
excluded sources are swappable via `IndexConfig` without modifying the core (`DEFAULT_INDEX_CONFIG`
= the standard above).

## Forward curve (1-factor Schwartz)

`d ln S = κ(ln θ − ln S) dt + σ dW` (mean-reversion, non-storable commodity, electricity analogy).
**Rust Monte-Carlo** engine (`forward_engine`, PyO3/maturin) for performance, **analytical
Python oracle** for parity (tested at 2%). Default calibration is **OLS AR(1)** (standard
Schwartz) with a robust half-life fallback for short history.

## Range, depth & anomalies (PoC status)

- **Snapshot depth**: the proprietary series starts at the **first collector run**;
  no retroactive depth (the price of compute has no history). At this stage
  `data/snapshots/` is empty as long as `VASTAI_API_KEY` is not provided.
- **Calibration history**: while the series remains thin, `run_build_curve.py` calibrates
  on a **demo-labeled synthetic** history; to be replaced by the real index series once
  collection has accumulated.
- **Tracked anomalies**: outliers (MAD rejection), phantom offers/survivorship (no carry-forward),
  look-ahead (point-in-time filter + dedicated test), real/simulated (flag + test).

## Run

```bash
uv sync --extra dev
# Rust engine (outside root pyproject, protected zone) :
uv run maturin develop -m projects/04_compute_index_curve/forward_engine/Cargo.toml
# Collect a real snapshot (requires VASTAI_API_KEY) :
uv run python -m infra.collectors.gpu_price_snapshot
# Build + log a forward curve (MLflow) :
uv run python projects/04_compute_index_curve/run_build_curve.py
# Tests :
uv run pytest projects/04_compute_index_curve
```

## Reproducibility

- **Data**: `data/snapshots` is versioned as plain git files — `git add`/`git commit`
  after each accumulation (`data/raw/<source>` stays local, gitignored by design).
- **MLflow**: `build_forward_curve` logs model, engine, calibrator, seed, n_paths,
  κ/θ/σ + git SHA (`experiments/mlruns`, `mlflow ui`). MLflow 2026 → `MLFLOW_ALLOW_FILE_STORE=true`.
