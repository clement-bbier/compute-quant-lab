---
paths:
  - "core/backtest/**"
  - "projects/**"
---
# Quantitative rigor (anti-bias)

- FORBIDDEN: using at instant t information not available at t (look-ahead).
  Features are computed only on past data (point-in-time).
- Explicitly model costs (fees, slippage) in every backtest.
- Strictly separate train / validation / test temporally (no random shuffle
  on time series).
- Every backtest result must be reproducible: seed fixed, git commit of the data
  logged, params logged in MLflow.
- Be suspicious of a Sharpe that looks too good: suspect overfitting / data snooping before celebrating.
