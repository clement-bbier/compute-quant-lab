# P02 — Spread Mean Reversion

**Mean-reversion** arbitrage strategy on the energy<->compute digital spark spread.
From the cointegration test to a reproducible backtest, reusing the lab's foundations
(**P01** pricing, **P08** backtest, `core.ingestion` compute leg).

## Pipeline

```
ENTSO-E (real energy) ─┐
                        ├─► core.pricing.SparkSpreadPricer (P01) ─► spread EUR/GPU·h
real compute snapshots ─┘                                            │
                                                                       ▼
            cointegration.py (EG MacKinnon + Johansen + half-life + rolling stability)
                                                                       │
                                                                       ▼
            strategy.MeanReversionStrategy (z-score hysteresis, ≤ t) ─► core.backtest (P08)
                                                                       │
                                                                       ▼
                                   MLflow run (params + metrics + git SHA + PnL figure)
```

## Modules (`src/`)
| File | Role |
|---|---|
| `cointegration.py` | ADF/KPSS, Engle-Granger (**MacKinnon p-value** via `coint`, anti-spurious), Johansen, OU half-life, point-in-time rolling re-estimation. |
| `strategy.py` | `MeanReversionStrategy(z_entry, z_exit, lookback)` — hysteresis band on the z-score ≤ t, reset at t==0. The `decide()` transition rule is the adjustable design point. |
| `data_sources.py` | Real loaders (ENTSO-E `load_energy_entsoe`, compute index `compute_index_series`) + `DataProvenance` (mandatory `simulated` flag) + `build_spread` via P01. |
| `run_backtest.py` | Real pipeline wired up, labeled simulated fallback, reproducible MLflow run. |

## Run

```bash
# Prerequisite (lab env): P08 Rust kernel compiled
uv sync --extra dev
uv run maturin develop -m core/backtest/_loop/Cargo.toml

# Tests (explicit invocation: see docs/decisions/002-per-project-ci-testpaths-gap.md)
uv run pytest projects/02_spread_mean_reversion -q

# Backtest + MLflow run (simulated until real data is wired up)
uv run python projects/02_spread_mean_reversion/src/run_backtest.py
```

### Real data (V5.3: on by default, zero key required)
- **Energy**: `load_energy_entsoe` reads the committed cold store (`data/cold/energy/`,
  FR/DE ENTSO-E day-ahead prices, 2024-01-01 → today) first — no token needed on a fresh
  clone. A live ENTSO-E token (`ENTSOE_API_TOKEN=…` in `.env`, free at
  <https://transparency.entsoe.eu/>) only refreshes beyond the store's committed range.
- **Compute**: still requires accumulated marketplace snapshots (`data/snapshots/`, built via
  `infra/collectors/gpu_price_snapshot.py` day by day; no cold store or retroactive history
  yet). Without snapshots, the pipeline falls back to the **labeled** simulated dataset
  (`simulated=True`).

`run_backtest.py` bounds the energy window to the real compute snapshots' own coverage (they're
much shallower than the energy cold store) — see [results/SYNTHESIS.md](results/SYNTHESIS.md) §1.

## Results & pitfalls
V5.3 reference run on **real** data (`entsoe_cold_store+marketplace`, `simulated=False`):
Sharpe ≈ 2.98 over ~1 month of real compute history — a preliminary read, not yet a validated
edge (short window, no walk-forward). Prior **simulated** reference (Sharpe ≈ 7.70) is kept for
comparison and was never credible (the strategy tracked the OU generating process exactly).
Full adversarial verdict (`/backtest-pitfalls`) and roadmap before any alpha claim:
[results/SYNTHESIS.md](results/SYNTHESIS.md).

## Tests (26, green)
Cointegration (detection + **rejection** of a non-cointegrated pair, anti-spurious), OU half-life,
point-in-time stability, z-score signal (entry/exit/hysteresis), **anti look-ahead** (P08 guard),
backtest determinism, mandatory real/simulated provenance.
