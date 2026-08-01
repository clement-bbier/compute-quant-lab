# P08 — Engine demo synthesis

> `results/last_run.json` and `results/mlruns/` are generated locally (gitignored,
> cf. `results/.gitignore`) — this document is the **committed** artifact backing the
> figures cited elsewhere (CLAUDE.md, README). Reproducible by construction (fixed seed):
> rerunning `uv run python projects/08_backtest_risk_engine/run_demo.py` regenerates
> exactly the same metrics.

## Reference run (SIMULATED)

- Strategy: `ZScoreMeanReversion` (window=32, z_scale=2.0) on a deterministic synthetic
  fixture (`demo_fixtures.py`, seed=42, 512 observations).
- Costs: fees 10 bps + slippage 5 bps (`LinearCostModel`).
- `n_trials = 1` (config fixed *a priori*, no hyperparameter search).

| Metric | Value |
|---|---:|
| Total PnL (capital=1) | 0.1150 |
| Sharpe (annualized) | **0.6154** |
| Max drawdown | -0.0468 |
| Turnover | 93.686 |
| Hit ratio | 0.4746 |

**Reading**: this is **not** an alpha claim — P08 is the **engine**, not a candidate
strategy. The point of this demo is to prove that the pipeline (look-ahead guard +
costs + Rust core + MLflow tracking) runs end-to-end and produces reproducible metrics.
A modest Sharpe (0.62) on a synthetic z-score mean-reversion setup is not suspicious
(unlike a very high Sharpe, cf. P02 §backtest-pitfalls).

## Reproducibility

Fixed seed (42), fixed summation order on the Rust core side (`backtest_loop`), bit-exact
parity with the Python oracle (`core/backtest/reference_loop.py`, tested). MLflow run
logged (params + metrics + git SHA + `dvc_version` — resolves to `no-dvc-data` in the
absence of versioned real data, cf. root CLAUDE.md).
