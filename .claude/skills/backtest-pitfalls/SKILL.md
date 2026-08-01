---
name: backtest-pitfalls
description: Anti-illusion checklist for any financial ML backtest (overfitting, p-hacking, selection bias). To be invoked systematically before trusting a result. Core of the risk-validator's job.
---
# Backtest Pitfalls (financial ML)

A backtest that shines is guilty until proven innocent. Distilled from financial ML
practice (López de Prado et al.).

## Checklist
1. **Look-ahead bias**: no feature must use future information. Check
   each feature line by line.
2. **Overfitting / model selection**: how many configurations were tried?
   The more you test, the more a good Sharpe arrives by chance (multiple testing). Document the
   number of trials; adjust (deflated Sharpe ratio).
3. **Temporal split**: no random shuffle on time series. Use a CV
   suited to time series (purged k-fold, embargo) to avoid leakage between train and test.
4. **Survivorship / universe selection**: the GPU universe changes (hosts entering/leaving).
   Do not retroactively condition on what survived.
5. **Realistic costs**: an alpha that dies after fees+slippage is not an alpha.
6. **Regime stationarity**: a model trained on one price regime can fail
   in the next regime. Test across multiple regimes.
7. **Reproducibility**: fixed seed, git-tracked data version, MLflow params. If you
   can't reproduce it, you can't trust it.

## Verdict
If any point fails → the result is not publishable. The risk-validator's role is to
actively hunt for these flaws, not to excuse them.

## Reference
`references/ml-finance-pitfalls/` (López de Prado, *Advances in Financial Machine Learning*).
