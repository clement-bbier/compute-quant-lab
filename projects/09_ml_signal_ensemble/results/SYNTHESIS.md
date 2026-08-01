# P09 — Synthesis & adversarial verdict

> Role held: **risk-validator** (adversary). At the time of this audit the dedicated agent
> did not yet exist in the environment (it has since been registered:
> `.claude/agents/risk-validator.md`) — the `/backtest-pitfalls` audit was therefore
> conducted by hand, actively hunting for flaws rather than excusing them.

## Reference run (SIMULATED)

- `run_id`: see `results/last_run.json` (MLflow under `results/mlruns/`).
- Data: `synthetic_spark_spread_gas_lead`, **`simulated=True`** — spark spread priced by
  P01, driven by a **weak** exogenous lead (gas) known with a publication lag (P07).
- Model: ensemble of 3 XGBoost models (seeds 11/22/33), purged k-fold (5) validation +
  embargo 5, horizon 1, neutral band 0.05. `n_trials = 1` (hyperparameters fixed *a priori*).

| Metric | Value | Reading |
|---|---:|---|
| Sharpe (annualized) | **0.17** | Near zero. |
| Deflated / Probabilistic Sharpe (PSR) | **0.66** | Modest probability that the true SR > 0. |
| Max drawdown | **-0.88** | Deep pullback → fragile strategy. |
| Turnover | **1050** (903 trades) | Very high: costs eat the signal. |
| Hit ratio | **0.24** | Low. |
| Total PnL (capital=1) | 0.43 | Positive but volatile. |

**Verdict: no alpha claimed.** The result is deliberately *unspectacular* — and that's the
point: validation rigor **did not manufacture** a false alpha. Compare with P02's
non-credible Sharpe of 7.70 (where the strategy fit the generating process too closely).

## `/backtest-pitfalls` checklist — item by item

1. **Look-ahead bias** — *covered.* Three stacked and **tested** defenses: features <= t
   (future-truncation invariance, `test_lookahead`/`test_pipeline`), label-horizon purge +
   embargo (`test_validation`), reading only `proba[view.t]` at execution time
   (`test_strategy`). No global normalization in the features (XGBoost = splits, scale
   invariant) → no scaling leakage. The synthetic's global `gas_std` lives in the **DGP**,
   never a feature.
2. **Overfitting / selection** — *controlled at PoC stage.* `n_trials = 1`, no hyperparameter
   search; the seed ensemble reduces variance, it is not selection. Warning: any future grid
   search (depth, thresholds, windows) **must** increment `n_trials` → the PSR will drop
   mechanically (`expected_max_sharpe` grows with the number of trials).
3. **Temporal split** — *correct.* Purged k-fold + embargo, **never shuffled**; a leaking
   splitter would turn `test_purge_removes_label_horizon_overlap` red.
4. **Survivorship / universe** — *N/A at PoC stage* (single synthetic series). On real data,
   the GPU universe has entries/exits: a hazard to handle when wiring up marketplaces.
5. **Realistic costs** — *modeled* (10 bps fees + 5 bps slippage, P08 engine). They
   **dominate** here (turnover 1050): this is precisely what kills the weak edge. Honest.
6. **Regime stationarity** — *not tested*: a single synthetic regime, drawdown -0.88 =
   fragility signal. Real data has regime breaks — an acknowledged limitation.
7. **Reproducibility** — *guaranteed.* Fixed seed, **deterministic** run (identical metrics
   on rerun), MLflow logs params + `n_trials` + git SHA + DVC version + PnL figure.

## What it would take to believe it (institutional tier)

- **Real** data (ENTSO-E + deep compute history) — the synthetic only proves the *pipeline*.
- **Reduce turnover**: the neutral-band / cost trade-off is real (a wider band ↓ turnover;
  cf. the `neutral_band` parameter) → cost-aware sizing, possibly a turnover penalty.
- **Deflated Sharpe with a real `n_trials`** as soon as tuning starts, **walk-forward**
  (not k-fold), multi-regime testing, LSTM/TFT + stacking.
- Have every result **stress-tested** by the `risk-validator` agent once it's created.
