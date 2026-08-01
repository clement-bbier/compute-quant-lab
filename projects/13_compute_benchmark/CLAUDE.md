# Project 13 — Compute Spot Benchmark (public index, data-product)

> LOCAL context. Global glossary and conventions: root CLAUDE.md. Detailed methodology
> and status: [README.md](README.md). **Showcase** layer (data-product + portfolio).

## Specific thesis
Package the **multi-venue compute spot index** as a **clean public benchmark**: the
"reference price of a GPU-hour" per model, with **cross-venue dispersion**.
Nobody has a clean, point-in-time compute price history → this is both a data-product
and a portfolio piece that demonstrates the end-to-end pipeline. Reuses everything existing.

## Owned modules
- `projects/13_compute_benchmark/` **only**.
- Read-only (consumption, never rewrite): `core.storage`, `core.ingestion`, `core.utils`.
- Protected zone untouched (`CLAUDE.md` root, `.claude/`, `.mcp.json`, `pyproject.toml`, `core/`).

## Architecture (SOLID / DI)
- **Lake read**: `core.storage.ParquetSnapshotStore` (versioned Parquet cold store).
- **Canonical aggregation**: `core.ingestion.build_spot_index` (P04, intra-venue distribution already corrected).
- **Pure layer (here)**: `src/benchmark/` — `index_series` (point-in-time series), `dispersion`
  (cross-venue stats + named levels), `report` (assembly + honest history state).
- **Isolated I/O**: `run_build_benchmark.py` (MLflow + `results/`), `dashboard/app.py` (Streamlit).

## Edge boundary (PUBLIC showcase — non-negotiable)
- We publish the **MEASUREMENT**: reference price (canonical **daily** fix at 00:30 UTC) +
  descriptive dispersion (spread, %, CV) + **average** level per named venue over the window.
- We do NOT publish the **DECISION**: no live timing signal "rent on X now"
  (private edge → WP). Granularity stays "benchmark", not "signal".

## Real / point-in-time
**Real** spot (provenance `real_spot`, never simulated). Everything UTC tz-aware. Anti look-ahead
inherited from `build_spot_index` (no observation `> as_of`); a fix without a fresh venue is **skipped**,
never filled by carry-forward. Short history at the start (accepted) — it grows.

## Progress status (PoC-now)
- [x] `index_series`: point-in-time index series (daily grid + demo cadence), tests green
- [x] `dispersion`: spread/%/CV + named levels; anti-drift invariant vs `build_spot_index`
- [x] `report`: multi-model assembly + honest `HistoryState`
- [x] `run_build_benchmark.py`: real MLflow run (`real_spot`) + `results/benchmark_summary.md`
- [x] `dashboard/app.py`: Streamlit demo (index + dispersion + levels)
- [ ] Convergence: `pyproject` testpaths `projects/13…/tests` (protected zone, out of WD scope)

## Launch
```bash
uv run pytest -q projects/13_compute_benchmark/tests
uv run python projects/13_compute_benchmark/run_build_benchmark.py   # reads data/snapshots
uv run streamlit run projects/13_compute_benchmark/dashboard/app.py
```
