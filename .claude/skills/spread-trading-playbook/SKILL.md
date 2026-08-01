---
name: spread-trading-playbook
description: Methodology for building a spread arbitrage strategy (here energy vs. compute) once cointegration is established. To be invoked to move from a statistical signal to a tradable strategy.
---
# Spread Trading Playbook

Assumes a validated cointegrated relationship (see /cointegration-analysis).

## Building the strategy
1. **Normalize the spread** as a z-score over a point-in-time rolling window.
2. **Entry/exit rules**: enter when |z| exceeds a threshold (e.g. 2), exit on reversion
   to 0. The threshold is a hyperparameter — optimize it WITH caution (see backtest-pitfalls).
3. **Sizing**: position inversely proportional to spread volatility; risk cap.
4. **Costs**: model fees + slippage. On an illiquid asset like compute,
   slippage dominates — be conservative.
5. **Stop / regime**: cut if the cointegration breaks down (the spread no longer reverts).

## Energy↔compute specifics
- The energy leg is liquid and has a deep history (ENTSO-E).
- The compute leg is illiquid, has little history, and uncertain execution. Treat
  the signal as indicative as long as the collected compute series is short;
  start with paper-trading.

## Validation metrics
Cumulative PnL, Sharpe, max drawdown, turnover, hit ratio, cost sensitivity.

## Reference
`references/stat-arb/` (Ernie Chan, *Algorithmic Trading*); `references/energy-markets/`.
