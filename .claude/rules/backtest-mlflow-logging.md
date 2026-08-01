---
paths:
  - "core/backtest/**"
  - "projects/**"
---
# Backtest reproducibility

- Every backtest MUST log an MLflow run containing: params, metrics, **git SHA**,
  and the **git commit** of the data. Use `core.backtest.tracking.tracked_run`
  (which composes `core.utils.tracking.run`).
- No strategy metric is published without a replayable MLflow run (`run_id`).
- Track the number of trials (`n_trials`) for multiple testing (deflated Sharpe
  at the institutional threshold). Works together with `backtest-runner` (execution)
  and `risk-validator` (adversary).
