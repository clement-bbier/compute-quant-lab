# P03 — GPU Volatility & Term Structure

Lab **Strategy** layer: treat GPU price **volatility** as an asset and
exploit the **term structure** of the forward curve (contango/backwardation) as a
directional signal. Consumes the foundational products of **P04** (spot index + forward).

## Data sources

| Leg | Real / Simulated | Source | Unit | Status |
|---|---|---|---|---|
| Spot index | **Real** | `core.ingestion.build_spot_index` on accumulated snapshots | $/GPU·h | wired (token-gated) |
| Forward curve | **SIMULATED** | P04 — 1-factor Schwartz seeded on spot | $/GPU·h / maturity | wired (Python MC fallback) |

> Warning: **Real/simulated boundary**: the term structure and signal derive from a
> `simulated=True` forward. `TermStructure.simulated` is a **required** field (no default);
> a test fails if it is absent. Never served as an observed market price.

## Methodology

### Volatility (pure numpy, causal)
- **Realized**: rolling standard deviation of log-returns over a trailing window (warmup → NaN).
- **EWMA** (RiskMetrics): `σ²_t = λ·σ²_{t-1} + (1-λ)·r²_t`, reactive, default λ 0.94.
- Annualization via named `periods_per_year` (compute traded 24/7 → 365).
- **Anti look-ahead**: `vol[t]` depends only on index returns ≤ t (tested by
  invariance to truncation). GARCH = extension point of the `VolEstimator` (Protocol).

### Term structure (pure)
- **Slope**: linear regression price ~ maturity (`np.polyfit` degree 1).
- **Curvature**: butterfly `F_short − 2·F_mid + F_long`.
- **Shape**: contango (slope > threshold), backwardation (slope < −threshold), else flat.

### Directional signal (roll-yield convention)
Non-storable commodities (electricity analogy): **backwardation → long (+1)**, **contango →
short (−1)**, neutral band → **0**. Inherits the `simulated` flag from the term structure.

## Range, depth & limitations (PoC status)
- **Short compute history**: the proprietary series starts at the first collection;
  while it remains thin, `run_analysis.py` runs on a **demo-labeled synthetic** spot
  (fixed seed) and switches to the real index once `data/snapshots/` is deep enough.
- **Simulated forward**: the curve's shape reflects the **model** (Schwartz
  mean-reversion), not an observed market anticipation. Any result is conditional.

## Run

```bash
uv sync --extra dev
# Full analysis (vol + term structure + signal) + MLflow run + results/ :
uv run python projects/03_gpu_vol_term_structure/src/run_analysis.py
# Tests (root testpaths does not yet include P03 -> explicit path) :
uv run pytest projects/03_gpu_vol_term_structure
```

## Reproducibility

- **MLflow**: `run_analysis.py` logs params (vol window, EWMA λ, `periods_per_year`,
  curve model, `forward_simulated`) + metrics (realized/EWMA vol, slope, curvature,
  signal) + git SHA via `core.utils.tracking` (`experiments/mlruns`, `mlflow ui`).
- **Seed** fixed everywhere. MLflow 2026 → `MLFLOW_ALLOW_FILE_STORE=true` (handled by `tracking`).

## Open items
Adding P03 to `testpaths` remains open (see `docs/decisions/002-per-project-ci-testpaths-gap.md`);
promoting the vol estimators to `core/` is undecided (a second consumer would confirm the need).
