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
                                   MLflow run (params + metrics + SHA + DVC + PnL figure)
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

### Wiring up REAL data
- **Energy**: create a free token at <https://transparency.entsoe.eu/> (My Account -> request
  API access, email to transparency@entsoe.eu, activated in ~24 h), then `ENTSOE_API_TOKEN=…` in `.env`.
- **Compute**: Vast.ai key (<https://vast.ai/> -> account -> API key) in `VASTAI_API_KEY`, then
  accumulate via the `infra/collectors/gpu_price_snapshot.py` collector (history builds up
  day by day; no retroactive compute data exists). Deeper alternative: Silicon Data
  SDH100RT (paid, `SILICONDATA_API_TOKEN`, not yet wired).

`run_backtest.py` automatically detects real data (token + snapshots present) and otherwise falls back to
the **labeled** simulated dataset `simulated=True`.

## Results & pitfalls
Reference run on **simulated** data: Sharpe ≈ 7.70 — **not credible** (the strategy tracks the
OU generating process exactly). The backtest validates the *pipeline*, not an alpha. Full adversarial verdict
(`/backtest-pitfalls`) and roadmap before any alpha claim: [results/SYNTHESIS.md](results/SYNTHESIS.md).

## Tests (22, green)
Cointegration (detection + **rejection** of a non-cointegrated pair, anti-spurious), OU half-life,
point-in-time stability, z-score signal (entry/exit/hysteresis), **anti look-ahead** (P08 guard),
backtest determinism, mandatory real/simulated provenance.
