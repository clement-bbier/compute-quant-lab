# Compute Spot Benchmark — publishable methodology

> The **reference price of a GPU-hour**, per model, with **cross-venue dispersion**.
> An external auditor should be able to reconstruct the index from this page.

## 1. What the benchmark measures

At a fix instant `t`, for a GPU model (e.g. H100), the benchmark publishes:

1. **Canonical index** `index(t)` — a single `$/GPU·h` price aggregating the marketplaces.
2. **Cross-venue dispersion** — how far venues deviate from this reference
   (absolute spread, spread %, coefficient of variation) + **which venue is on average
   cheaper** over the window.

> **Edge boundary.** The benchmark publishes a **measurement**, not a **decision**. The
> granularity is the **daily fix**; no live timing signal ("rent on X
> now") is distributed — that belongs to separate private research.

## 2. Underlying data (real, point-in-time)

- Source: on-demand price snapshots from GPU marketplaces accumulated 24/7 — 7 connected
  providers (`core/ingestion/providers/`: Cudo, DataCrunch, Hyperstack, PrimeIntellect,
  RunPod, TensorDock, Vast.ai), of which PrimeIntellect relays several more underlying
  venues, for **15 active venues** in the current cold store
  (`results/benchmark_summary.md`). Stored in a **versioned Parquet cold store**
  (`core.storage`, append-only, idempotent). Provenance `real_spot` — never simulated.
- Unit: **USD per GPU-hour**. **UTC** tz-aware timestamps.
- ⚠️ **Short history at the start.** Compute pricing has no deep public history:
  it's being accumulated. The index is therefore thin at launch (cf. `results/benchmark_summary.md`),
  and grows every day. This is acknowledged, not hidden.

## 3. Index construction (canonical method)

Reuses `core.ingestion.build_spot_index` (GPU Markets / Silicon Data standard, CME
compute futures settlement). For a fix at `as_of`:

1. **Filtering**: keep only the desired `gpu_model`, `lease_type = on_demand`, excluding
   hyperscaler list prices (AWS/GCP/Azure excluded from the estimator), and **point-in-time** —
   only `snapshotted_at ≤ as_of`.
2. **Staleness (no carry-forward)**: keep only readings within the 24 h window
   preceding the fix. A venue whose latest reading is stale is **ignored**, not carried forward.
3. **Per-venue reduction**: per marketplace, take the freshest cohort of readings
   and its **median** (robust to noise from an isolated offer; availability summed).
4. **Outlier rejection**: **MAD** filter (2.5 median absolute deviations) on per-venue rates.
5. **Aggregation**: **20% trimmed mean** of the retained rates → `index(t)`.

Each point carries its audit metadata: `method`, `n_sources`, `oldest_obs_at`.
The method is **injectable** (`IndexConfig`): estimator, filter, window are swappable.

### Fix grid
- **Published product**: **daily** fix at 00:30 UTC (`daily_fix_grid`). A day's fix
  *settles after the fact*: the 24 h staleness window captures the elapsed day.
- **Demo**: cadence per observed snapshot (`observed_fix_grid`) to visualize a thin
  history — clearly labeled "demo", this is not the product granularity.

## 4. Cross-venue dispersion

On the venues **retained by the index** (after outlier rejection), at each fix:

- `spread_abs = max − min` (`$/GPU·h`); `spread_pct = spread_abs / index(t)`;
- `cv` = population standard deviation / mean (coefficient of variation);
- `cheapest_venue` / `dearest_venue` (named).
- **Single-venue** (`n_venues < 2`, e.g. a model on a single marketplace) → dispersion
  **undefined** and flagged (`is_defined = False`): we don't manufacture a fictional dispersion.

**Average levels per venue** (`venue_levels`): over the window, average `$/h` level and
**average discount vs. index** per named venue (negative = cheaper than the reference). This is
the descriptive answer to "who is cheaper on average" — static, never a live signal.

### Anti-drift safeguard
`dispersion` re-implements the index's per-venue reduction (`core` being read-only).
An invariant test guarantees no drift:
`estimator(filter(venue_rates_at(...))) == build_spot_index(...).price`.

## 5. Reproducibility

`run_build_benchmark.py` logs an **MLflow** run (`compute_benchmark`): aggregation
parameters (method, staleness, fix frequency, window, models), metrics (number of fixes,
mean spread %, history state), **git SHA** + **DVC version** of the data, tag
`provenance=real_spot`. Since the versioned cold store is immutable, a run replayed on the same
DVC version is reproducible. Summary written to `results/benchmark_summary.md`.

## 6. Run it

```bash
# data/snapshots is versioned as plain git directly on main, updated continuously
# by the CI cron — nothing to check out, the local clone already has it.

uv run pytest -q projects/13_compute_benchmark/tests          # tests
uv run python projects/13_compute_benchmark/run_build_benchmark.py   # run + results/
uv run streamlit run projects/13_compute_benchmark/dashboard/app.py  # demo dashboard
```

## 7. Known limitations

- Short history (accumulation started 2026-06-22) → series and averages are not yet
  very statistically significant while the window is young.
- 15 venues active as of this run (`results/benchmark_summary.md`) → the MAD filter and
  trimmed mean are live and filtering on most multi-venue models; single-venue models
  (e.g. RTX3080, RTX6000ADA) still report dispersion as undefined by design (§4).
- Venue survivorship: a marketplace disappearing biases the history (to monitor).
- `on_demand` only (spot/reserved not aggregated — standard practice, never mix lease types).
