# Project 01 — Digital Spark Spread Model

> LOCAL context. The global glossary and conventions live in the root CLAUDE.md.

## Specific thesis
Compute, day by day, the theoretical profitability of a datacenter (compute price vs.
energy cost) to detect when compute is over- or under-valued, and derive
energy <-> compute arbitrage signals from it.

## Data
- Energy: ENTSO-E spot price (FR/DE), EUR/MWh, UTC.
- Compute: H100 rental price (Vast.ai / RunPod), EUR/h/GPU.

## Roadmap (institutional tier, not yet built)
1. Ingestion (core.ingestion) -> data/raw/
2. Quality check (/data-quality-check) -> data/processed/
3. Point-in-time features + D+7 electricity prediction model (XGBoost)
4. Signal generation (core.pricing.spark_spread)
5. Backtest (/run-backtest) on 2025 -> results/
6. Streamlit dashboard (dashboard/): actual vs. predicted curve, cumulative PnL, Sharpe.

## Progress status
- [x] Spark spread pricing module (core/pricing) + tests
- [x] ENTSO-E connector (`src/prepare_dataset.py:fetch_energy_entsoe`, token-gated,
  synthetic fallback when `ENTSOE_API_TOKEN` is absent — not yet promoted to
  `core/ingestion/providers/`)
- [ ] GPU price connector (Silicon Data leg is still a documented stub)
- [ ] Prediction model
- [ ] 2025 backtest
- [ ] Dashboard

## Key results
Demo run (synthetic energy fallback, Silicon Data stub, region FR / H100, 2025-01-01 to
2025-01-31): mean spread **2.024 EUR/GPU·h** (100% positive hours), dominated by the
compute leg (energy is only ~5.3% of the compute rental price). Breakeven electricity
price ≈ **EUR 1,677/MWh**. Full detail: [results/SYNTHESIS.md](results/SYNTHESIS.md).
