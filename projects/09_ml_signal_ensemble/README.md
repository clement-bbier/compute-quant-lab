# P09 — ML Signal Ensemble (spark spread direction)

Directional ML ensemble on the **digital spark spread**, backtestable **glue-free** via
the P08 engine's `Strategy` interface. The central discipline is **anti-overfitting**:
strict temporal validation (purged CV + embargo), deflated Sharpe, logged `n_trials`.

## Pipeline

```
core.features (P07, <=t)  ┐
spread P01 (lags/roll <=t) ├─►  X  ──►  PurgedKFold + embargo  ──►  OOS proba  ─┐
label = sign(Δspread_{t+h})┘            (XGBoost ensemble, oos_predict)         │
                                                                                ▼
                          PrecomputedSignalStrategy.signal(view) = pos(proba[view.t])
                                                                                │
                                       P08 backtest engine (GuardedView) → PnL/Sharpe
```

**Three stacked anti-look-ahead defenses**: (a) point-in-time features (reuses the P07
guard), (b) purge + embargo in the CV (the prediction for `t` never sees its future), (c)
`GuardedView` at execution time (inherited from P08, free).

## Run it

```bash
# 1. Rust core of the P08 engine (prerequisite for a real backtest — like P05)
uv run maturin develop -m core/backtest/_loop/Cargo.toml --release

# 2. Model layer tests (pure logic; requires the Rust core to import core.backtest)
uv run pytest core/models/tests -q

# 3. Headline run (training + backtest + MLflow, on SIMULATED data)
uv run python projects/09_ml_signal_ensemble/src/run_train.py

# 4. Project tests (smoke + provenance; skipped without the Rust core)
uv run pytest projects/09_ml_signal_ensemble/tests -q
```

The run logs an MLflow run under `results/mlruns/` (params + `n_trials` + git SHA + DVC
version + PnL figure) and writes `results/last_run.json`. Dashboard: `mlflow ui`.

## Reusable building blocks promoted into `core/models/`

| Module | Role |
|---|---|
| `protocols` | `Model` / `Splitter` contracts (DI). |
| `validation` | `PurgedKFold`, `oos_predict`, `deflated_sharpe_ratio`, `expected_max_sharpe`. |
| `pipeline` | `FeaturePipeline` (consumes `core.features`), `build_labels`, `SpreadFeatureSpec`. |
| `xgboost_model` | `XGBoostDirectionModel` (deterministic), `SeedBaggingEnsemble`. |
| `strategy` | `PrecomputedSignalStrategy` (adapter to `core.backtest`). |

## Status & honesty
PoC on **labeled simulated data** (`provenance.simulated=True`). **Modest result, not sold
as alpha**: the full adversarial verdict (`/backtest-pitfalls` checklist) lives in
[results/SYNTHESIS.md](results/SYNTHESIS.md). The institutional tier (real data,
walk-forward, LSTM/TFT, deflated Sharpe with a real `n_trials`) is listed as future work
in the [CLAUDE.md](CLAUDE.md) progress status above.
