# Project 03 — GPU Volatility & Term Structure

> LOCAL context. Global glossary and conventions: root CLAUDE.md. Methodology and status:
> [README.md](README.md).

## Specific thesis
GPU price **volatility** is an asset in its own right, and the **term structure** of the
forward curve (contango/backwardation) carries directional information. P03 estimates
the realized vol of the compute spot index and analyzes the term structure of the SIMULATED forward.

## Modules owned
- `projects/03_gpu_vol_term_structure/` ONLY.
- Forbidden (read-only): any `core/`, root protected zone (`CLAUDE.md`, `.claude/`,
  `.mcp.json`, `pyproject.toml`). Promotions to `core/` → convergence patches.

## Upstream dependencies (P04, in `main`)
- **REAL spot index**: `core.ingestion.build_spot_index` (one fix point-in-time per `as_of`).
- **SIMULATED forward**: `projects/04_compute_index_curve/src/forward` (1-factor Schwartz),
  consumed via `sys.path` insertion (import `forward.build_curve`). Warning: never real.

## Architecture (SOLID / DI, pure logic)
- **Vol**: `VolEstimator` (Protocol) → `RealizedVol`, `EwmaVol` (pure numpy, causal).
  GARCH = documented extension point (no `arch` dependency without convergence).
- **Term structure**: pure `TermStructureAnalyzer` → `TermStructure` (slope/curvature/shape).
- **Signal**: `directional_signal` (roll-yield convention: backwardation→long).
- **Glue**: `spot_series.build_spot_series` replays `build_spot_index` over a grid.

## Real/simulated boundary (non-negotiable)
`TermStructure.simulated` is REQUIRED (no default), propagated into `DirectionalSignal`.
Everything derived from the forward is `simulated=True`. Dedicated test (`test_simulated_flag.py`)
fails if the flag is absent (rule `forward-real-simulated`).

## Progress status (PoC-now)
- [x] Realized vol + EWMA estimators (pure numpy), anti look-ahead tested
- [x] Term structure analysis (slope/curvature/contango-backwardation shape)
- [x] Directional roll-yield signal (backwardation→long)
- [x] Point-in-time spot series glue (consumes `core.ingestion`)
- [x] `run_analysis.py`: logged MLflow run + `results/` synthesis
- [ ] GARCH (institutional tier, convergence for the `arch` dependency)
- [ ] Calibrate on the real spot series once snapshots have accumulated
- [ ] Promote `VolEstimator`/estimators to `core/` (convergence)

## Key results
Realized/EWMA vol of the spot index + term structure shape of the SIMULATED forward
(+ signal), replayable MLflow run. Details: [README.md](README.md) / [results/](results/).
