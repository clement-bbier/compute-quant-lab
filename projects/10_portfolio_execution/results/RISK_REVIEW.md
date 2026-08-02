# P10 — Adversarial review (risk-validator work, done inline)

> At the time of this review, the `risk-validator` agent did not yet exist in
> `.claude/agents/` (it has since been registered). Its discipline was applied
> here by hand: **attack the net PnL**, hunt for look-ahead / overfitting / underestimated costs
> (skill `/backtest-pitfalls`).

## P12 update (2026-06-22) — **real** signals wired in (P02/P06/P09)
The desk now runs on the real producers from `core.signals` (run `cfcd48b6…`). The review
below (written in the mock era) **still holds**, with three aggravating factors to record:
- **Gross positive but artifactual**: +0.506 (Sharpe 1.24) on a mean-reverting synthetic
  series — the signals track the OU generator. **Don't mistake this for alpha** (same trap as P02).
- **Net much worse**: **−4.47** (vs −0.54 for mocks), turnover **455** (vs 86.5). The real signals
  churn ×5 → costs dominate even more. Point 5 below is **reinforced**.
- **Point 3 now ACTIVE**: the ML is *fitted*. P09's probability is OOS purged-CV (anti-overfit)
  but **not strictly walk-forward causal** (a future fold can train the model that predicts a past row).
  At runtime the guard is clean; the *construction* of the probability is not → **to be attacked**.

**Convergence action**: create the `risk-validator` agent and have it attack the **aggregated
net** (turnover, ML causality, P06/P09 correlation) on real data. As long as it's synthetic: **alpha = 0**.

## Verdict (mock era — kept for history)
**No alpha is claimed.** The PoC validates a *desk mechanism*, not a strategy. The
net PnL (−0.54) is negative and that's the **expected and honest** result: the producers are
mocks with no edge. Publishing this number as performance would be a mistake — it only measures
the correctness of the pipeline.

## `/backtest-pitfalls` checklist
1. **Look-ahead** — done. Neutralized by construction: the decision at `t` goes through P08's
   `GuardedView` (≤ t); a cheating producer raises `LookAheadError` (`test_desk_lookahead`). The
   weighting vol only uses lagged realized returns.
2. **Overfitting / multiple testing** — done, at the PoC stage: `n_trials=1`, parameters fixed
   *a priori*, no optimization. Warning: once real signals and tuning are introduced → deflated Sharpe mandatory.
3. **Temporal splitting** — done. No shuffle (sequential engine). N/A here (nothing is *fitted*);
   to be reinstated (walk-forward, embargo) once P09/ML feeds the desk.
4. **Survivorship / universe** — warning: not covered — a single synthetic series. The real GPU
   universe changes (hosts entering/leaving) → to be addressed once real signals are wired in.
5. **Realistic costs** — done. Core of the project: linear costs + convex impact, **PnL judged on net**.
   The sensitivity analysis shows the high turnover (86.5) makes the strategy fragile to costs.
6. **Regime stationarity** — warning: a single simulated regime. Test multi-regime before any conclusion.
7. **Reproducibility** — done. Fixed seed, MLflow run (params + git SHA), `last_run.json` snapshot.

## Blind spots specific to aggregation (§10)
- **Ignored correlations**: inverse-vol weights by marginal vol, not by joint risk contribution.
  Two strongly correlated signals (e.g. P06 and P09 on the same factor) would be
  over-allocated → false sense of diversification. **Action**: `ERCScheme` (risk-parity) at the
  institutional tier; the seam already exists.
- **Composite overconfidence**: aggregating signals that are each individually overfitted produces
  a flattering net PnL *in-sample*. **Action**: attack the aggregated net on out-of-sample data,
  not each signal in isolation.
- **Underestimated costs**: κ and bps are assumptions. **Action**: calibrate against real
  executions; capacity (impact depending on notional/liquidity) isn't modeled yet.

## What it would take to believe a future positive result
Real signals (P02/P06/P09), out-of-sample multi-regime testing, calibrated costs, deflated Sharpe,
and correlation-aware weighting. Until these conditions are met: **pipeline OK,
alpha = 0**.
