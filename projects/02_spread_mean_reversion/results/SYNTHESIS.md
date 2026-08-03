# P02 — Backtest synthesis & adversarial verdict

> Reference run: `last_run.json` (seed 42, **REAL data**, `simulated=False`,
> `source=entsoe_cold_store+marketplace`). Execution cross-check: `backtest-runner`
> (isolated). Adversarial audit: `/backtest-pitfalls` checklist.

## 1. Result (REAL run, `simulated=False`) — V8.1

FR ENTSO-E day-ahead prices from the committed cold store (`data/cold/energy/`) + the H100
compute index reconstructed from real accumulated marketplace snapshots
(`data/snapshots/`). The compute leg only has ~1 month of real history
(2026-06-22 → 2026-07-21) — the energy window is bounded to that same span (see §2), not the
cold store's full 2024-2026 range, to avoid a 2.5-year ffill-flat compute price.

The ENTSO-E grid is **quarter-hourly** (modal gap 15 min, confirmed on the committed cold
store: 29,288 15-min gaps vs. 15,334 60-min gaps per region), not hourly — annualization uses
`PERIODS_PER_YEAR = 35040` (4x8760), corrected from the previously published 8760.

| Metric | Value |
|---|---|
| Total PnL | 0.962 |
| **Sharpe (annualized √35040)** | **5.96** |
| Sharpe t-stat (n_obs=2,807, grid) | 1.69 |
| Sharpe t-stat (n_obs=441, compute-effective) | 0.67 |
| Sharpe 95% CI (grid) | [−0.96, 12.89] |
| Sharpe 95% CI (compute-effective) | [−11.51, 23.44] |
| Max drawdown | −19.2 % |
| Turnover | 106.0 |
| Hit ratio | 0.202 |
| n_trades | 106 |
| n_obs (grid, 15-min ticks) | 2,807 |
| n_obs_compute_effective (distinct collector runs) | 441 |

**Honest reading**: at either sample size, the t-stat is well under the ~1.96 threshold for
95% significance and both CIs straddle zero — **this Sharpe is not statistically
distinguishable from zero.** The grid figure (2,807) overstates independence: most 15-min
ticks as-of-carry the same underlying compute reading, so 441 (distinct marketplace
collector runs) is the more honest denominator — and it makes the uncertainty even wider, not
narrower. Neither number supports treating 5.96 as a validated edge.

Cointegration diagnostics (in-sample, on the real aligned series): EG p ≈ 3.2e-05
(cointegrated), Johansen n_relations = 2, half-life ≈ 30.6 h, hedge ratio ≈ −0.00019.

## 1bis. Prior SIMULATED reference run (kept for comparison, flagged non-credible)

| Metric | Value |
|---|---|
| Total PnL | 4.068 |
| Sharpe (annualized √8760) | 7.70 |
| Max drawdown | −20.6 % |
| Turnover | 90.0 |
| Hit ratio | 0.17 |
| n_trades | 90 |

This earlier run (`source=synthetic_cointegrated_ou`, `simulated=True`, 2,000 hourly obs)
never had a `last_run.json` committed — this SYNTHESIS.md was written before the pipeline had
ever actually executed end-to-end. The 7.70 Sharpe was constructed data where the strategy
tracks its own OU generating process exactly (see §3 below for why it's not credible).

**Neither number is informative, for different reasons — this is not a "correction toward
credibility" story.** The 7.70 simulated Sharpe is non-credible by construction (the strategy
fits the generating process it was tested on). The 5.96 real-data Sharpe is non-credible by
sample size (t-stat 0.67–1.69, CI spans zero at both readings above). Going from "definitely
not real" to "possibly real but we can't yet tell" is not evidence of improvement — it is two
different kinds of "don't believe this number yet."

## 2. Cointegration found?

**Yes, on real data**: Engle-Granger p ≈ 3.2e-05 (rejects the null of no cointegration well
below the 5% threshold), Johansen also detects 2 relations. Caveat: the compute leg is only
~1 month deep (real marketplace history is young — no cold store for compute yet, unlike
energy), so this cointegration finding **cannot yet be trusted as a stable long-run
relationship** — it is measured over too short a window to rule out a spurious short-sample
coincidence, and has not been re-estimated on a rolling basis. Revisit once `data/snapshots/`
accumulates enough months to test stability out of sample.

## 3. Adversarial verdict (`/backtest-pitfalls`) — is the Sharpe 5.96 credible? **NO — not statistically distinguishable from zero.**

| # | Pitfall | Severity | Handled by the code? |
|---|---|---|---|
| 1 | **Look-ahead** | Low | Yes: P08 `GuardedView` guard active (red test `view.at(t+1)` -> `LookAheadError`); z-score on ≤ t. Warning: the run's cointegration *diagnostic* is full-sample (not the signal) -> should be gated via `rolling_cointegration`. |
| 2 | **Overfitting / multiple testing** | Low | Yes: `n_trials=1`, z-thresholds fixed a priori (not optimized), tracked in MLflow. No: deflated Sharpe not applied (required as soon as scanning occurs). |
| 3 | **Walk-forward / OOS** | **High** | No: everything in-sample, and the sample itself is only ~1 month (bounded by compute snapshot history, not energy's own depth). No train/test split, no purged-embargo CV. |
| 4 | **Short real-data window** | **High** | No: n_obs_compute_effective = 441 (distinct collector runs) is thin for a cointegration+mean-reversion claim. t-stat 0.67 (effective) / 1.69 (grid) — the 95% CI spans zero at both readings ([−11.5, 23.4] and [−0.96, 12.9] respectively). The finding could still reflect one lucky month rather than a persistent relationship. |
| 5 | **Sharpe annualization** | Medium (corrected) | Fixed: the ENTSO-E grid is quarter-hourly, not hourly (modal gap 15 min, confirmed on the committed cold store) — annualization now uses √35040, not √8760. Residual caveat unchanged: annualizing **autocorrelated** returns (mean reversion) still inflates the reported Sharpe relative to a lower-frequency measure. |
| 6 | **Realistic costs (illiquid compute)** | **High** | No: 15 bps round-trip is optimistic — on fragmented compute markets **slippage dominates** (cf. `/spread-trading-playbook`), shorting GPU rentals is difficult/impossible, capacity is limited. Symmetric linear cost model is unrealistic. |
| 7 | **Spurious cointegration** | Medium | Partial: correct discipline — **MacKinnon** p-value via `coint` (not a raw ADF), tested to *reject* two independent random walks on synthetic fixtures. But the real p-value here is only validated in-sample on one short window. |
| 8 | **Reproducibility** | — | Yes: seed + bit-exact determinism (Python oracle) + MLflow (params/metrics/git SHA) + `n_trials`. Real data versioned via the committed cold store (`entsoe_cold_store` provenance) — a genuine improvement over the earlier unversioned synthetic run. |

**Most serious flag**: real data now flows end-to-end (a genuine improvement over the earlier
never-executed synthetic reference), but the compute leg's ~1-month, 441-observation history
means the Sharpe's own confidence interval spans zero — this is a **preliminary read, not a
validated edge, and not distinguishable from noise at this sample size.** Do not read the
higher post-correction Sharpe (5.96 vs. the previously published 2.98) as "the strategy got
better" — it is the same result under a corrected annualization factor; the statistical
uncertainty is unchanged in kind and, if anything, wider once measured on the honest n=441.

## 4. Before believing in any alpha (actionable)

1. **Deeper compute history**: the energy leg is now fully real and deep (2024-2026 via the
   cold store); compute is the remaining bottleneck (~1 month) — accumulate more marketplace
   snapshots before trusting the cointegration finding.
2. **Point-in-time cointegration gating**: decide to enter the market based on `rolling_cointegration`
   (≤ t), never on the full-sample diagnostic.
3. **Walk-forward / OOS** with purged k-fold + embargo (anti temporal leakage) — needs more
   history to be meaningful.
4. **Deflated Sharpe** as soon as a z-threshold is swept (Bailey & Lopez de Prado).
5. **Realistic compute execution model**: dominant slippage, asymmetry, short/capacity constraints.
6. **Honest annualization frequency** (daily, or de-annualize) instead of √35040 on
   autocorrelated returns — the quarter-hourly correction (§3 item 5) fixed the *factor*, not
   the underlying autocorrelation-inflation caveat.
7. **Report uncertainty, not a point estimate**: any future headline number should carry its
   t-stat/CI (`core.models.validation.sharpe_t_stat`/`sharpe_confidence_interval`) alongside
   both the grid and compute-effective sample sizes, as done in §1 here.

## 5. Governance note

At the time of the original audit, the `risk-validator` agent described in the root
`CLAUDE.md` §6 was not yet registered in this environment, so that review was conducted
manually via the `/backtest-pitfalls` checklist. The agent has since been created
(`.claude/agents/risk-validator.md`). This V5.3 update (real-data rerun) was likewise
reviewed manually against the same checklist.
