# P01 — Digital Spark Spread Pricer

Point-in-time pricer for the **digital spark spread**: compute revenue (GPU
rental) minus the energy cost of producing it (electricity × PUE). The
foundation every downstream project (P02 mean-reversion, P05 regional basis,
P06 futures, P09 ML ensemble) builds its spread on.

## Pipeline

```
ENTSO-E (real energy, or a labeled synthetic fallback) ─┐
                                                          ├─► core.pricing.SparkSpreadPricer
Silicon Data / compute index (real or labeled stub)  ────┘        │
                                                                    ▼
                                                    spread EUR/GPU·h, point-in-time
                                                                    │
                                                                    ▼
                                        MLflow run (params + metrics + git SHA)
```

## Modules (`src/`)
| File | Role |
|---|---|
| `prepare_dataset.py` | Loads the energy leg (real via `ENTSOE_API_TOKEN`, else a deterministic synthetic fallback) and the compute leg (Silicon Data stub). |
| `run_pricer.py` | Runs `core.pricing.SparkSpreadPricer` over the window, logs params/metrics/git SHA to MLflow, writes `results/run_summary.json`. |

## Run

```bash
uv sync --extra dev

# Data (real if ENTSOE_API_TOKEN is in .env, otherwise a logged synthetic fallback)
uv run python projects/01_digital_spark_spread/src/prepare_dataset.py

# Pricing + MLflow run + run_summary.json
uv run python projects/01_digital_spark_spread/src/run_pricer.py

mlflow ui --backend-store-uri experiments/mlruns   # params + metrics + git SHA
```

### Wiring up real data
- **Energy**: free token at <https://transparency.entsoe.eu/> (My Account ->
  request API access), then `ENTSOE_API_TOKEN=…` in `.env`.
- **Compute**: `SiliconDataSource` is a documented stub
  (`core/ingestion/compute_index.py`) pending a real SDH100RT-style index;
  until then, pricing runs on the stub series.

`run_pricer.py` picks up real data automatically as soon as a token is
present; it falls back to a **labeled** synthetic series otherwise.

## Results (synthetic run, region FR / H100)
Reference window 2025-01-01 → 2025-01-31 (744h, UTC), 8x H100 (TDP 700W, PUE
1.82). Full detail and sensitivity table:
[results/SYNTHESIS.md](results/SYNTHESIS.md).

| Metric (EUR/GPU·h) | Value |
|---|---|
| Mean spread | 2.024 |
| Mean revenue (compute) | 2.137 |
| Mean cost (energy) | 0.113 |
| % positive hours | 100% |

The marginal energy cost of a GPU-hour is only ~5.3% of the compute rental
price under this regime — the spread is dominated by the compute price, not
the energy leg. See the sensitivity table in `SYNTHESIS.md` for the
breakeven electricity price (~EUR 1,677/MWh) at which the margin disappears.

**Honesty note**: this reference run uses the synthetic energy fallback (no
`ENTSOE_API_TOKEN` in the session that produced it) and the compute stub —
it demonstrates the pricer's mechanics, not a market edge measured on real
data.

## Tests
Anti-look-ahead (bit-identical spread when future rows are appended), UTC/FX
point-in-time handling (naive datetimes rejected), Rust↔Python kernel parity
(`np.allclose` on 10,000 points). Tests live in the root [`tests/`](../../tests)
directory (`test_pricer.py`, `test_pricer_parity.py`, etc.) — see
[docs/decisions/002-per-project-ci-testpaths-gap.md](../../docs/decisions/002-per-project-ci-testpaths-gap.md)
for why.
