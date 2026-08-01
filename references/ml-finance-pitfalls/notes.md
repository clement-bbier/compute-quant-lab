# Financial ML pitfalls — notes

> Distilled protocol + pointers. No copyrighted text is copied here — see
> `references/bibliography.md` for full citations.

Referenced by `.claude/skills/backtest-pitfalls`, the core methodology
behind the `risk-validator` agent.

## Source

**Lopez de Prado, M.**, *Advances in Financial Machine Learning* — the
reference treatment of how standard ML practice silently breaks on
financial time series, and the fixes that make a backtest trustworthy:

- **Backtest overfitting**: the more configurations are tried, the more a
  good Sharpe ratio arrives by chance alone (multiple testing). The number
  of trials must be tracked and the result corrected for it (see deflated
  Sharpe ratio below).
- **Purged k-fold cross-validation**: plain k-fold leaks information between
  train and test on time series because adjacent folds overlap in the
  label's time window. Purging removes training samples whose label window
  overlaps the test window; an embargo further removes samples immediately
  after the test window, closing the leakage from serial correlation.
- **Deflated Sharpe ratio**: adjusts the observed Sharpe ratio for the
  number of trials and the non-normality of returns, giving a Sharpe that is
  no longer inflated by search over configurations.
- **Meta-labeling**: a secondary model that learns *whether to act* on a
  primary model's signal (sizing/filtering), rather than folding that
  decision into a single monolithic model.

## The checklist

The full anti-illusion checklist (look-ahead, overfitting, temporal split,
survivorship, costs, regime stationarity, reproducibility) lives in
`.claude/skills/backtest-pitfalls/SKILL.md` — this file exists only to point
back to where these concepts come from. `core.models.validation` implements
`PurgedKFold` and the deflated Sharpe ratio directly from this source.
