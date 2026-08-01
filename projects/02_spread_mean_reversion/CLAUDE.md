# Project 02 — Spread Mean Reversion

> LOCAL context. Global glossary and conventions: root CLAUDE.md. Detailed methodology
> and status: [README.md](README.md). Protected-zone patches: [CONVERGENCE.md](CONVERGENCE.md).

## Specific thesis
If the energy leg (ENTSO-E) and the compute leg (GPU marketplaces) are **cointegrated**, the
spark spread priced by **P01** temporarily deviates from its long-term equilibrium and then reverts.
We bet on this mean reversion (z-score with a hysteresis band), backtested by the **P08** engine.

## Owned modules
- `projects/02_spread_mean_reversion/` only.
- Read-only: `core.pricing` (P01), `core.backtest` (P08), `core.ingestion` (compute leg).
- Forbidden: any `core/`, root protected zone -> patches go to [CONVERGENCE.md](CONVERGENCE.md).

## Architecture (SOLID / DI)
- `src/cointegration.py` — full protocol: ADF/KPSS, Engle-Granger (**MacKinnon** p-value via
  `coint`, not a raw ADF -> anti-spurious), Johansen, OU half-life, point-in-time rolling re-estimation.
- `src/strategy.py` — `MeanReversionStrategy(z_entry, z_exit, lookback)` implements the `Strategy`
  Protocol from P08: z-score on a window <= t, hysteresis band (entry/exit), reset at t==0.
- `src/data_sources.py` — real loaders (ENTSO-E + compute index from snapshots); `simulated`
  provenance is **mandatory** (rule `forward-real-simulated`); `build_spread` via P01.
- `src/run_backtest.py` — real pipeline wired up, labeled simulated fallback, reproducible MLflow run.

## Real/simulated boundary (non-negotiable)
`DataProvenance.simulated` is mandatory (no default); a test fails if it is missing. Real data
(ENTSO-E + marketplaces) is never mixed with simulated data without an explicit label.

## Progress status (PoC-now)
- [x] Full cointegration analysis (EG + Johansen + half-life + rolling stability), anti-spurious tested
- [x] Hysteresis mean-reversion strategy, anti look-ahead (P08 guard), determinism
- [x] Integration with P01 (spread pricing) + P08 (backtest) + `core.ingestion` (compute leg)
- [x] Reproducible MLflow run (params + metrics + SHA + DVC + PnL figure + simulated flag + n_trials)
- [x] 22 tests green; `ruff`/`mypy core` green
- [ ] **Real data**: ENTSO-E token (registration in progress) + accumulating compute snapshots
- [ ] Institutional tier (3b): deflated Sharpe, walk-forward, dynamic sizing, execution

## Key results
Pipeline validated end-to-end on a **SIMULATED** dataset (provenance `simulated=True`). Warning:
the synthetic Sharpe is **not credible** (the strategy tracks the OU generating process exactly): see the
adversarial verdict in [results/SYNTHESIS.md](results/SYNTHESIS.md). No alpha is claimed until
the backtest has run on real data.
