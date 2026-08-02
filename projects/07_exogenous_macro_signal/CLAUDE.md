# Project 07 — Exogenous Macro Signal

> LOCAL context. Global glossary and conventions: root CLAUDE.md.

## Specific thesis
**Exogenous** variables (gas price, HDD/CDD weather) **lead** the moves of the
energy leg, and therefore the spark spread (P01). P07 builds these
**point-in-time** features in `core/features/` (reusable by P09 ML) and measures
their *lead* over the spread — without look-ahead or overfitting.

## Risk #1: LOOK-AHEAD (macro data delayed + revised)
Each observation carries two timestamps: `value_ts` (period described) and
`knowledge_ts = value_ts + publication lag` (publication date). A feature at
`t` only uses `knowledge_ts <= t`. **Revisions** = several vintages per
`value_ts`; at `t` we only see the latest one published in time. Modeled in
`core.features.as_of_snapshot`, with a test that fails if the guard is
removed (`core/features/tests`).

## Architecture
- `core/features/` (owned module, foundation): `protocols.py` (vintage contracts,
  `ExogenousSource`, `FeatureBuilder`), `builders.py` (`as_of_snapshot`,
  `from_lagged_series`, `assert_point_in_time` guard, pure transforms,
  `PointInTimeFeatureBuilder`).
- `projects/07_…/src/`: `sources.py` (I/O, deterministic synthetic fallback),
  `analysis.py` (cross-correlation + confirmation OLS, pure), `run_signal.py`
  (orchestration + MLflow).

## Reproducibility
MLflow run via `core.utils.tracking.run` (params: variables, publication lags,
windows, seed; git SHA tag). Raw exogenous data → `data/raw/exogenous/`, local
cache (gitignored by design, never committed).

## ERCOT branch (L0 grid-stress, REAL data)
Sub-pipeline distinct from the gas/HDD/CDD signal above: measures whether the
ERCOT **reserve margin** and **net-load gradient** (predictors frozen at L0
pre-registration,
`docs/superpowers/specs/2026-06-23-L0-ercot-grid-stress-preregistration.md`) predict
an RTM spike, out of sample.
- `src/ercot_dataset.py` (97 L) — rebuilds point-in-time predictors from the cold
  store (`as_of ≈ 6pm CPT D-1`), anti-look-ahead guard on `publish_time <= as_of`.
- `src/ercot_labels.py` (67 L) — spike labels (intraday percentile, absolute threshold).
- `src/ercot_baseline.py` (46 L) — reference climatology baseline.
- `src/ercot_calibration.py` (98 L) — purged K-fold + embargo (`core.models`), comparison
  to the baseline, bootstrap CI + Benjamini-Hochberg multi-spec correction.
- `src/ercot_eval.py` (79 L) — PR-AUC metrics + statistical tests.
- `src/run_ercot_calibration.py` (70 L) — orchestration → MLflow run.
- 457 LOC total, 14 dedicated tests in `tests/test_ercot_*.py`.

Reads **exclusively** from the real ERCOT cold store (`data/cold/ercot`, rule
`training-cold-store`) — never a synthetic fallback, unlike the rest of P07.
This worktree does not contain the populated cold store (`data/cold/` is empty
except for `.gitkeep`): the 14 tests pass on fixtures, but `run_ercot_calibration.py`
needs a real backfill beforehand (`infra/collectors/ercot_backfill.py --start ... --end ...`,
requires `GRIDSTATUS_API_KEY`).

## Progress status (PoC-now ✅)
- [x] Point-in-time mechanics (lag + revisions) in `core/features/` + 16 tests.
- [x] STRICT anti-look-ahead under test (publication lag, guard).
- [x] Point-in-time builders (lags, moving averages, diffs) on known fixtures.
- [x] Anti-overfit lead measurement: cross-correlation + out-of-sample OLS (temporal split).
- [x] Reproducible MLflow run + raw exogenous data in local cache (`data/raw/`, gitignored by design).

## Key results (SIMULATED data, seed=7)
DGP injecting a 3-day lead; the pipeline recovers **2 exploitable days** (the 1-day
publication lag eats 1 day of lead time):
- best feature **gas_price_lag0**, lead **2 days**, **|corr| ≈ 0.65**;
- `hdd_lag0` confirms (≈ 0.65); `cdd` ≈ 0 (consistent negative control);
- OLS confirmation: coef < 0, p-value ≈ 4e-45, **R²_oos ≈ 0.35** (predictive, not overfit).

**Pitfalls covered**: publication lag (under test), revisions (vintages), UTC
timezone, spurious regression (measured on **changes**, not levels).
**Out of scope (institutional)**: real weather/gas connector (`data-engineer`),
nowcasting, causal model, large panel, fine-grained handling of real revisions.

## Convergence
Adding this project's tests to `testpaths` remains an open gap: see
`docs/decisions/002-per-project-ci-testpaths-gap.md`.
