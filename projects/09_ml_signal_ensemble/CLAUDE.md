# Project 09 — ML Signal Ensemble

> LOCAL context. Global glossary and conventions: root CLAUDE.md. Detailed methodology
> and status: [README.md](README.md). Protected-zone patches: [CONVERGENCE.md](CONVERGENCE.md).

## Specific thesis
Forecast the **direction of the spark spread** (P01) with an **ML ensemble** fed by
point-in-time exogenous features (P07) and spread-derived features. The signal is
evaluated by the P08 backtest engine. In finance + ML, **enemy #1 is overfitting**:
temporal validation rigor trumps model complexity.

## Owned modules
- **`core/models/`** (reusable building block) **+** `projects/09_ml_signal_ensemble/`.
- Read-only: `core.pricing` (P01), `core.features` (P07), `core.backtest` (P08).
- Off-limits: everything else in `core/`, root protected zone (`CLAUDE.md`, `.claude/`, `.mcp.json`,
  `pyproject.toml`) → patches in [CONVERGENCE.md](CONVERGENCE.md).

## Architecture (SOLID / DI) — `core/models/`
- `protocols.py` — `Model` (`fit`/`predict_proba`), `Splitter`: injectable contracts (DI).
- `validation.py` — `PurgedKFold` (horizon purge + embargo, **never shuffled**), `oos_predict`
  (aligned OOS vector), `deflated_sharpe_ratio` (anti multiple-testing).
- `pipeline.py` — `FeaturePipeline` (consumes `core.features` P07 + causal spread features),
  `build_labels` (sign of the forward return).
- `xgboost_model.py` — `XGBoostDirectionModel` (deterministic), `SeedBaggingEnsemble`.
- `strategy.py` — `PrecomputedSignalStrategy`: adapter to P08's `Strategy` Protocol
  (reads `proba[view.t]`, maps to a position via a neutral band).

## Key insight (ML → backtest bridge)
P08 only passes the `Strategy` a point-in-time view of the **price series**, not the
feature matrix. So we precompute an **OOS probability** vector (purged-CV) aligned on
the index, and the adapter just reads it at `view.t`. The model never sees prices at
runtime → any leakage is neutralized *upstream*, and the `GuardedView` guard stays free
(OCP).

## Real/simulated boundary (non-negotiable)
`synthetic.DataProvenance.simulated` is **mandatory** (no default, `forward-real-simulated`
rule); a test fails if it's missing. At PoC stage, everything runs on **labeled simulated**
data (not blocked on ENTSO-E).

## Progress status (PoC-now)
- [x] `core/models/`: protocols, purged-CV + embargo + OOS, deflated Sharpe, PIT pipeline, deterministic
  XGBoost + seed ensemble, `Strategy` adapter — 30 passing tests.
- [x] Anti-look-ahead (3 defenses), leak-free temporal split, determinism, pure-noise sanity check.
- [x] Simulated headline run → P08 backtest → MLflow (params + n_trials + SHA + DVC + PnL figure).
- [x] Adversarial verdict `/backtest-pitfalls` ([results/SYNTHESIS.md](results/SYNTHESIS.md)).
- [x] `ruff` / `mypy core` / `pytest` all green.
- [ ] **Real data** (ENTSO-E + compute history); **walk-forward**; LSTM/TFT (tier 3b).
- [ ] `risk-validator` agent (protected zone → convergence, cf. CONVERGENCE.md).

## Key results
Pipeline validated end-to-end on **SIMULATED** data. Sharpe ~0.17, deflated/PSR ~0.66, deep
drawdown, high turnover: the weak synthetic edge **does not survive costs**. **No alpha
claimed** — see the verdict in [results/SYNTHESIS.md](results/SYNTHESIS.md).
