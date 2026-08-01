# P05 — Energy ↔ Compute Basis

Measures the spark spread **basis** between regions (FR/DE): the point-in-time difference
of regional spreads, each spread adjusted by local **PUE**. PoC objective: quantify the
basis amplitude, its sensitivity to PUE, its dislocations and their persistence — and
honestly expose why this is not (yet) an executable arbitrage.

## Idea

At equal FX and compute price between regions, compute revenue cancels out and

```
basis[r] = spread[r] − spread[ref] = power_kw·(pue_ref·energy_ref − pue_r·energy_r) / 1000
```

The basis is therefore, at PoC stage, a **PUE-weighted electricity price spread**. This is
intentional and acknowledged: compute pricing does not (yet) have regional granularity.

## Architecture (SOLID / DI)

| File | Role |
|---|---|
| `src/region_config.py` | `RegionConfig` (PUE, TDP, n_gpus, FX) + `build_regional_pricer` → a `SparkSpreadPricer` (P01) **per region** |
| `src/basis.py` | **pure** `BasisCalculator` (point-in-time inner join) + `detect_dislocations` (threshold + AR(1) half-life) |
| `src/data.py` | I/O: ENTSO-E FR/DE energy (labeled synthetic fallback) + P04 compute index (labeled fallback) |
| `src/run_basis.py` | Orchestration → MLflow run → `results/SYNTHESIS.md` |

Reused read-only: `core.pricing` (P01), `core.ingestion` (P04),
`core.utils.config` / `core.utils.tracking`. No writes outside `projects/05_…`.

## Methodology

- **Point-in-time**: the pricer aligns compute on the energy grid via backward as-of join;
  the basis aligns regional spreads via an **inner join** (no fabricated value).
- **PUE injected** per region (config, no magic number). Sensitivity tested (monotone).
- **Dislocations**: `|basis| > z·std` → p95 amplitude + fraction of time dislocated.
  **Persistence**: AR(1) half-life `ln(2)/−ln(φ)` (`None` if not mean-reverting).
- **Real/synthetic boundary**: `energy_source` / `compute_source` logged in MLflow.

## Run

```bash
# P05 tests (until the convergence testpaths patch lands, run explicitly)
uv run pytest projects/05_energy_compute_basis -q
uv run ruff check . && uv run mypy core

# full pipeline + MLflow run + results/SYNTHESIS.md
uv run python projects/05_energy_compute_basis/src/run_basis.py
mlflow ui   # dashboard (experiment p05_energy_compute_basis)
```

> Real data: set `ENTSOE_API_TOKEN` (energy); without a token, a **clearly labeled**
> deterministic synthetic fallback is used. Real compute comes from P04 snapshots if
> accumulated.

## Results

- `results/SYNTHESIS.md` — basis amplitude, PUE sensitivity, execution limitations
  (regenerated on every run).
- `results/RISK_REVIEW.md` — adversarial review (look-ahead, false arbitrage, PUE
  assumption, persistence, overfitting) + guardrails before any tradable signal.

## Limitations (PoC) & next steps

Regional PUE = a strong, poorly observable assumption; global compute → basis driven by
energy; transfer costs/latency ignored. Institutional tier: optimized load routing,
capacity constraints, real data, out-of-sample tradable signal (see `RISK_REVIEW.md`).
