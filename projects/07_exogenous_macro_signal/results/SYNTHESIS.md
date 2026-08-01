# P07 — Synthesis: exogenous macro signal (lead over the spread)

> **SIMULATED** data (deterministic fallback, fixed seed): a demonstration of
> point-in-time method, not a claim of realism. A real weather/gas
> connector remains a `data-engineer` backlog item.

## Observed lead
- Best feature: **gas_price_lag0**
- Optimal lead: **2 day(s)** (the DGP injects a 3-day lead).
- |correlation| at lead: **0.651**

## OLS confirmation (strict temporal split, no shuffling)
- coef = -0.0035, p-value = 3.72e-45
- in-sample R² = 0.457, **out-of-sample R² = 0.346**
- n_train = 328, n_test = 141

## Look-ahead pitfalls covered
- Explicit publication lag (knowledge_ts = value_ts + lag) — red-first test.
- Late revisions: only the vintage published in time is seen (vintages).
- UTC tz-aware alignment (naive datetime rejected).
- Anti-overfit lead measurement: cross-correlation + out-of-sample OLS.

MLflow run: `6863042e4aa14ca3bb65151c981a7d97` — raw exogenous data: local_cache (data/raw/, gitignored by design).
