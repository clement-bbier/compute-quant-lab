# Bibliography — the lab's canon

> Distilled methodology + pointers to the works. No copyrighted text is
> copied: actionable protocols are encoded (see the skills) and sources are cited.

## Statistical arbitrage & cointegration
- Engle, R. & Granger, C. (1987), *Co-integration and Error Correction* — the founding test.
- Johansen, S. — multivariate cointegration test (preferred for >= 2 series).
- Avellaneda, M. & Lee, J. (2010), *Statistical Arbitrage in the U.S. Equities Market*.
- Chan, E., *Algorithmic Trading: Winning Strategies and Their Rationale* — practical application.
-> Distilled methodology: `.claude/skills/cointegration-analysis`, `spread-trading-playbook`.

## Financial ML pitfalls (CRITICAL for risk-validator)
- Lopez de Prado, M., *Advances in Financial Machine Learning* — backtest
  overfitting, purged k-fold, deflated Sharpe, meta-labeling.
-> Distilled methodology: `.claude/skills/backtest-pitfalls`.

## Energy markets & derivatives
- Eydeland, A. & Wolyniec, K., *Energy and Power Risk Management*.
- Clewlow, L. & Strickland, C., *Energy Derivatives: Pricing and Risk Management*.
- The *spark spread* concept (gas->electricity) comes from this literature;
  here it is adapted into the *digital spark spread* (electricity->compute).
-> Notes: `references/energy-markets/`.

## Time series & forecasting
- Hyndman, R. & Athanasopoulos, G., *Forecasting: Principles and Practice* (free online).
- Models: XGBoost (baseline), LSTM / Temporal Fusion Transformer (sequential).

## Reference data sources (connectors)
- ENTSO-E Transparency Platform — EU electricity spot price (official, free, deep history).
- S&P Global / Kensho — institutional financial data (MCP connected).
- Tavily — structured web search for scouting (MCP connected).
