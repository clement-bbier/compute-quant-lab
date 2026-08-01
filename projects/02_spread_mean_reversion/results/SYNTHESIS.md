# P02 — Backtest synthesis & adversarial verdict

> Reference run: `last_run.json` (seed 42, 2000 hourly obs, **SIMULATED data**).
> Execution cross-check: `backtest-runner` (isolated). Adversarial audit: `/backtest-pitfalls` checklist.

## 1. Result (SIMULATED run, `simulated=True`)

| Metric | Value |
|---|---|
| Total PnL | 4.068 |
| **Sharpe (annualized √8760)** | **7.70** |
| Max drawdown | −20.6 % |
| Turnover | 90.0 |
| Hit ratio | 0.17 |
| n_trades | 90 |

Cointegration diagnostics (in-sample): EG p ≈ 1.9e-08 (cointegrated), Johansen n_relations = 2,
half-life ≈ 15.2 h, hedge ratio ≈ 0.0022. **Determinism confirmed** (bit-for-bit identical
metrics across two runs, `backtest-runner`).

## 2. Cointegration found?
On the simulated dataset, **yes**, by construction (compute = energy cost + stationary OU). But it's
an **artifact**: Johansen sees full rank (2 relations for 2 series = both series judged
stationary) because the coupling to energy is tenuous (hedge ratio 0.0022) -> compute is dominated
by the OU process and *appears* stationary. This is **not** a clean cointegrated I(1) system. To be redone on
real data.

## 3. Adversarial verdict (`/backtest-pitfalls`) — is the Sharpe credible? **NO.**

| # | Pitfall | Severity | Handled by the code? |
|---|---|---|---|
| 1 | **Look-ahead** | Low | Yes: P08 `GuardedView` guard active (red test `view.at(t+1)` -> `LookAheadError`); z-score on ≤ t. Warning: the run's cointegration *diagnostic* is full-sample (not the signal) -> should be gated via `rolling_cointegration`. |
| 2 | **Overfitting / multiple testing** | Low | Yes: `n_trials=1`, z-thresholds fixed a priori (not optimized), tracked in MLflow. No: deflated Sharpe not applied (required as soon as scanning occurs). |
| 3 | **Walk-forward / OOS** | **High** | No: everything in-sample. No train/test split, no purged-embargo CV. |
| 4 | **Sharpe 7.70 not credible** | **High** | No: (a) synthetic data where the strategy tracks the OU generating process exactly (zero model risk); (b) hourly annualization √8760 on **autocorrelated** returns (mean reversion) -> inflated Sharpe (≈ ÷5 on a daily basis); (c) hit_ratio 0.17 + Sharpe 7.7 -> PnL concentrated on few trades (skewed distribution, fragile to timing). |
| 5 | **Spurious cointegration** | Medium | Yes: correct discipline — **MacKinnon** p-value via `coint` (not a raw ADF), tested to *reject* two independent random walks. No: but only validated in-sample. |
| 6 | **Realistic costs (illiquid compute)** | **High** | No: 15 bps round-trip is optimistic — on fragmented compute markets **slippage dominates** (cf. `/spread-trading-playbook`), shorting GPU rentals is difficult/impossible, capacity is limited. Symmetric linear cost model is unrealistic. |
| 7 | **Reproducibility** | — | Yes: seed + bit-exact determinism + MLflow (params/metrics/SHA/DVC) + `n_trials`. `dvc_version=no-dvc-data` (expected: no real data versioned). |

**Most serious flag**: the result is **not an alpha** — it is an infrastructure validation
on simulated data whose generator is known. The high Sharpe is *expected* and misleading.

## 4. Before believing in any alpha (actionable)
1. **Real data**: ENTSO-E energy (token in progress) + compute history (paid Silicon Data
   or accumulated Vast.ai/RunPod snapshots).
2. **Point-in-time cointegration gating**: decide to enter the market based on `rolling_cointegration`
   (≤ t), never on the full-sample diagnostic.
3. **Walk-forward / OOS** with purged k-fold + embargo (anti temporal leakage).
4. **Deflated Sharpe** as soon as a z-threshold is swept (Bailey & Lopez de Prado).
5. **Realistic compute execution model**: dominant slippage, asymmetry, short/capacity constraints.
6. **Honest annualization frequency** (daily, or de-annualize) instead of √8760 on
   autocorrelated returns.

## 5. Governance note
At the time of this audit, the `risk-validator` agent described in the root `CLAUDE.md` §6
was not yet registered in this environment, so this review was conducted manually via the
`/backtest-pitfalls` checklist. The agent has since been created (`.claude/agents/risk-validator.md`).
