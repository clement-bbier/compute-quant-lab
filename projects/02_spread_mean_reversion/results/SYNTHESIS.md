# P02 — Backtest synthesis & adversarial verdict

> Reference run: `last_run.json` (seed 42, **REAL data**, `simulated=False`,
> `source=entsoe_cold_store+marketplace`). Execution cross-check: `backtest-runner`
> (isolated). Adversarial audit: `/backtest-pitfalls` checklist.

## 1. Result (REAL run, `simulated=False`) — V5.3

FR ENTSO-E day-ahead prices from the committed cold store (`data/cold/energy/`) + the H100
compute index reconstructed from real accumulated marketplace snapshots
(`data/snapshots/`). The compute leg only has ~1 month of real history
(2026-06-22 → 2026-07-21) — the energy window is bounded to that same span (see §2), not the
cold store's full 2024-2026 range, to avoid a 2.5-year ffill-flat compute price.

| Metric | Value |
|---|---|
| Total PnL | 0.962 |
| **Sharpe (annualized √8760)** | **2.98** |
| Max drawdown | −19.2 % |
| Turnover | 106.0 |
| Hit ratio | 0.202 |
| n_trades | 106 |
| n_obs | 2,807 (hourly, ~1 month) |

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
tracks its own OU generating process exactly (see §3 below for why it's not credible). The
real run's lower Sharpe (2.98, still elevated — see §3) is a **downward correction toward
credibility**, exactly what real data replacing a self-referential simulation should produce.

## 2. Cointegration found?

**Yes, on real data**: Engle-Granger p ≈ 3.2e-05 (rejects the null of no cointegration well
below the 5% threshold), Johansen also detects 2 relations. Caveat: the compute leg is only
~1 month deep (real marketplace history is young — no cold store for compute yet, unlike
energy), so this cointegration finding **cannot yet be trusted as a stable long-run
relationship** — it is measured over too short a window to rule out a spurious short-sample
coincidence, and has not been re-estimated on a rolling basis. Revisit once `data/snapshots/`
accumulates enough months to test stability out of sample.

## 3. Adversarial verdict (`/backtest-pitfalls`) — is the Sharpe 2.98 credible? **NOT YET.**

| # | Pitfall | Severity | Handled by the code? |
|---|---|---|---|
| 1 | **Look-ahead** | Low | Yes: P08 `GuardedView` guard active (red test `view.at(t+1)` -> `LookAheadError`); z-score on ≤ t. Warning: the run's cointegration *diagnostic* is full-sample (not the signal) -> should be gated via `rolling_cointegration`. |
| 2 | **Overfitting / multiple testing** | Low | Yes: `n_trials=1`, z-thresholds fixed a priori (not optimized), tracked in MLflow. No: deflated Sharpe not applied (required as soon as scanning occurs). |
| 3 | **Walk-forward / OOS** | **High** | No: everything in-sample, and the sample itself is only ~1 month (bounded by compute snapshot history, not energy's own depth). No train/test split, no purged-embargo CV. |
| 4 | **Short real-data window** | **High** | No: ~2,800 hourly observations is thin for a cointegration+mean-reversion claim. The finding could still reflect one lucky month rather than a persistent relationship. |
| 5 | **Sharpe annualization** | Medium | No: hourly annualization √8760 on **autocorrelated** returns (mean reversion) inflates the reported Sharpe relative to a daily-frequency measure — same caveat as the earlier simulated run, unresolved here. |
| 6 | **Realistic costs (illiquid compute)** | **High** | No: 15 bps round-trip is optimistic — on fragmented compute markets **slippage dominates** (cf. `/spread-trading-playbook`), shorting GPU rentals is difficult/impossible, capacity is limited. Symmetric linear cost model is unrealistic. |
| 7 | **Spurious cointegration** | Medium | Partial: correct discipline — **MacKinnon** p-value via `coint` (not a raw ADF), tested to *reject* two independent random walks on synthetic fixtures. But the real p-value here is only validated in-sample on one short window. |
| 8 | **Reproducibility** | — | Yes: seed + bit-exact determinism (Python oracle) + MLflow (params/metrics/git SHA) + `n_trials`. Real data versioned via the committed cold store (`entsoe_cold_store` provenance) — a genuine improvement over the earlier unversioned synthetic run. |

**Most serious flag**: real data now flows end-to-end (a genuine improvement over the earlier
never-executed synthetic reference), but the compute leg's ~1-month history makes this a
**preliminary read, not a validated edge**. The lower, still-elevated Sharpe is consistent
with "some of the earlier inflation is gone" rather than "this is now trustworthy alpha."

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
6. **Honest annualization frequency** (daily, or de-annualize) instead of √8760 on
   autocorrelated returns.

## 5. Governance note

At the time of the original audit, the `risk-validator` agent described in the root
`CLAUDE.md` §6 was not yet registered in this environment, so that review was conducted
manually via the `/backtest-pitfalls` checklist. The agent has since been created
(`.claude/agents/risk-validator.md`). This V5.3 update (real-data rerun) was likewise
reviewed manually against the same checklist.
