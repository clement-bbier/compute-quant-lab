---
name: cointegration-analysis
description: Rigorous protocol to test whether two series (electricity price and compute price) are linked by a stable relationship exploitable for arbitrage. To be invoked before building any spread or mean-reversion strategy.
---
# Cointegration Analysis

Two series can be correlated by chance (spurious correlation) without any lasting
relationship. Cointegration tests for a true long-run equilibrium relationship — it is the
statistical foundation of a spread arbitrage. Never short a spread without having tested it.

## Protocol

1. **Stationarity**: test each raw series with ADF (Augmented Dickey-Fuller) and
   KPSS. A price series is typically I(1) (non-stationary in level, stationary
   in first difference). Confirm before going further.
2. **Cointegration test**:
   - Engle-Granger (2 series): regress y on x, test the residual for stationarity (ADF).
     If the residual is stationary → cointegration.
   - Johansen (≥ 2 series, more robust): prefer it to estimate the cointegration vector
     and the number of relationships.
3. **The spread** = stationary linear combination coming out of the test. This is what you trade,
   not the raw prices.
4. **Mean-reversion half-life**: estimate via an Ornstein-Uhlenbeck model (regression
   of Δspread on the lagged spread). A short half-life = a more exploitable signal.
5. **Stability**: re-test on rolling windows. A relationship that only appears over
   one period is suspect. Cointegration can break down (regime change).

## Pitfalls (delegate the check to risk-validator)
- In-sample cointegration not verified out-of-sample.
- Look-ahead: the cointegration vector must be estimated point-in-time, re-estimated
  on a rolling window, never on the whole sample at once.

## Tools
`statsmodels`: `adfuller`, `coint` (Engle-Granger), `coint_johansen` (via vecm).

## Reference
See `references/stat-arb/` (Engle-Granger 1987; Johansen; Avellaneda & Lee).
