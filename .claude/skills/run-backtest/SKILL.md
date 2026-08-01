---
name: run-backtest
description: Standard procedure to run and log a compute/energy arbitrage strategy backtest reproducibly. To be invoked whenever a strategy or signal needs to be evaluated.
---
# Run Backtest

Reproducible protocol. Follow the steps in order, without skipping any.

1. **Freeze the context**: capture the current git SHA and the data version
   (`git log -1 -- data/`). Refuse to run if the git tree is dirty (`git status` non-empty).
2. **Load the data** via `core.ingestion` (never a hardcoded path). Verify
   it has gone through `core.data_quality` (otherwise, run /data-quality-check first).
3. **Temporal split**: chronological train/val/test, no shuffle.
4. **Run** the `core.backtest` engine with a fixed seed.
5. **Mandatory metrics**: cumulative PnL, Sharpe ratio, max drawdown, turnover,
   hit ratio. Costs (fees + slippage) modeled.
6. **Log to MLflow**: params, metrics, git SHA, data version, PnL figure.
   Store artifacts in `projects/NN/results/`.
7. **Sanity check**: if Sharpe > 2 on real data, flag a risk of
   overfitting/look-ahead and delegate a review to the `risk-validator` subagent.
