# P07 — Exogenous Macro Signal

Measures whether **exogenous** variables (gas price, HDD/CDD weather) **lead**
moves in the energy leg, and therefore the spark spread (P01) — point-in-time,
with an explicit publication lag and no look-ahead. Also promotes the
point-in-time feature-engineering primitives into `core/features/`, reused by
P09's ML ensemble.

## Two sub-pipelines

1. **Gas/weather lead signal** (synthetic demonstration of method)
2. **ERCOT grid-stress branch** (real data, pre-registered hypothesis)

### 1. Gas/weather lead signal

```
gas price / HDD / CDD ──(publication lag, revisions)──► core.features.as_of_snapshot
                                                                  │
                                                                  ▼
                                            cross-correlation + out-of-sample OLS
                                                                  │
                                                                  ▼
                                              MLflow run + results/SYNTHESIS.md
```

Every observation carries `value_ts` (period described) and `knowledge_ts =
value_ts + publication lag`; a feature at `t` only ever uses `knowledge_ts <=
t`. Modeled in `core/features/builders.py` (`as_of_snapshot`), with a test
that fails if the guard is removed.

| File (`src/`) | Role |
|---|---|
| `sources.py` | I/O: real if `EXOGENOUS_API_TOKEN` is set (connector not yet wired — falls back to synthetic regardless), otherwise a deterministic synthetic fallback injecting a known lead. |
| `analysis.py` | Cross-correlation + confirmation OLS (pure), out-of-sample split. |
| `run_signal.py` | Orchestration + MLflow run + `results/SYNTHESIS.md` generation. |

```bash
uv sync --extra dev
uv run maturin develop -m core/backtest/_loop/Cargo.toml
uv run maturin develop -m core/pricing/_kernel/Cargo.toml
uv run maturin develop -m projects/04_compute_index_curve/forward_engine/Cargo.toml

uv run pytest core/features/tests projects/07_exogenous_macro_signal/tests -q
uv run python projects/07_exogenous_macro_signal/src/run_signal.py
```

**Results (simulated, seed=7)**: the synthetic data-generating process
injects a 3-day lead; the pipeline recovers 2 exploitable days (the 1-day
publication lag eats one day of the lead). Best feature `gas_price_lag0`,
lead 2 days, |corr| ≈ 0.65; OLS confirmation R²_oos ≈ 0.35 (p ≈ 4e-45).
Full detail: [results/SYNTHESIS.md](results/SYNTHESIS.md).

### 2. ERCOT grid-stress branch (real data)

A separate sub-pipeline testing whether the ERCOT **reserve margin** and
**net-load gradient** — predictors frozen at pre-registration time, see
[docs/superpowers/specs/2026-06-23-L0-ercot-grid-stress-preregistration.md](../../docs/superpowers/specs/2026-06-23-L0-ercot-grid-stress-preregistration.md)
— predict a real-time-market price spike, out of sample.

| File (`src/`) | Role |
|---|---|
| `ercot_dataset.py` | Point-in-time predictors from the real ERCOT cold store (`as_of` ≈ 6pm CPT D-1), anti-look-ahead guard on `publish_time <= as_of`. |
| `ercot_labels.py` | Spike labels (intraday percentile, absolute threshold). |
| `ercot_baseline.py` | Climatology reference baseline. |
| `ercot_calibration.py` | Purged K-fold + embargo (`core.models`), bootstrap CI, Benjamini-Hochberg multi-spec correction. |
| `ercot_eval.py` | PR-AUC metrics + statistical tests. |
| `run_ercot_calibration.py` | Orchestration → MLflow run. |

This branch reads **exclusively** from the real ERCOT cold store
(`data/cold/ercot`, rule `training-cold-store`) — never a synthetic fallback.
The 14 dedicated tests (`tests/test_ercot_*.py`) pass on fixtures; running
`run_ercot_calibration.py` for real needs a populated cold store first:

```bash
# Requires GRIDSTATUS_API_KEY in .env
uv run python -m infra.collectors.ercot_backfill --start <date> --end <date>
uv run python projects/07_exogenous_macro_signal/src/run_ercot_calibration.py
```

## Real/simulated boundary
The gas/weather signal is synthetic by construction until
`EXOGENOUS_API_TOKEN` is wired to a real connector (currently a documented
gap — the token being present does not yet activate real data, see
`sources.py`). The ERCOT branch is real data end to end, or it doesn't run.
Neither is ever mixed with the other without an explicit label.

## Tests
16 tests in `core/features/tests` (point-in-time mechanics: lag, revisions,
UTC alignment) + tests under `projects/07_exogenous_macro_signal/tests`
(analysis, ERCOT dataset/labels/baseline/calibration/eval — 14 of these on
the ERCOT branch). Run in isolation per
[docs/decisions/002-per-project-ci-testpaths-gap.md](../../docs/decisions/002-per-project-ci-testpaths-gap.md).
