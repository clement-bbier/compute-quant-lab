# Project 01 — Digital Spark Spread Model

> LOCAL context. The global glossary and conventions live in the root CLAUDE.md.

## Specific thesis
Compute, day by day, the theoretical profitability of a datacenter (compute price vs.
energy cost) to detect when compute is over- or under-valued, and derive
energy <-> compute arbitrage signals from it.

## Data
- Energy: ENTSO-E spot price (FR/DE), EUR/MWh, UTC.
- Compute: H100 rental price (Vast.ai / RunPod), EUR/h/GPU.

## Target pipeline
1. Ingestion (core.ingestion) -> data/raw/
2. Quality check (/data-quality-check) -> data/processed/
3. Point-in-time features + D+7 electricity prediction model (XGBoost)
4. Signal generation (core.pricing.spark_spread)
5. Backtest (/run-backtest) on 2025 -> results/
6. Streamlit dashboard (dashboard/): actual vs. predicted curve, cumulative PnL, Sharpe.

## Progress status
- [x] Spark spread pricing module (core/pricing) + tests
- [ ] ENTSO-E connector
- [ ] GPU price connector
- [ ] Prediction model
- [ ] 2025 backtest
- [ ] Dashboard

## Key results
_(to be filled in)_
