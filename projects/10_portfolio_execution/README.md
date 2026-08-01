# P10 — Portfolio & Execution

**Desk** layer of the lab: aggregate signals into a portfolio under a risk budget,
model **execution and costs**, and judge the strategy on **net PnL**.

## Why this layer
P01–P09 produce *signals* (spreads, futures, vol, ML…). None of them says **how much to put on**
or **what's left after fees**. P10 answers that: it's the layer that turns a
collection of views into a tradable portfolio and measures its realistic PnL.

## Decoupling & parallelism
P10 consumes the `Strategy` / `PointInTimeView` abstraction from **P08** (`core.backtest`). The
mocked producers remain for regression tests; the **real** P02/P06/P09 signals
(promoted into `core.signals`, P12) are wired in behind the same `SignalProducer` Protocol,
without touching the desk's code (OCP). This let P10 run **in parallel** with the signal projects.

## Architecture
```
signals P02/P06/P09 (real) ──► DeskStrategy (composite P08 Strategy)
   (s_i ∈[-1,1])      │   at each t:
                      │   1. s_i,t via GuardedView ≤ t          (signals.py)
                      │   2. point-in-time realized vol          (desk.py)
                      │   3. inverse-vol weights + budget        (portfolio.py)
                      │   4. net position = clip(Σ w_i s_i)
                      ▼
        P08 engine (no cost) ──► GROSS returns + positions
                      ▼
        ExecutionModel  ──► costs (linear + κ·Δ²) ──► NET PnL   (execution.py)
                      ▼
        MLflow run: params + net/gross metrics + attribution + figure  (run_desk.py)
```

### Design decisions
- **Weighting**: inverse-vol `w_i = (b_i/σ_i)/Σ_j(b_j/σ_j)` at the PoC stage, behind `WeightScheme`
  (OCP seam) which opens the door to **risk-parity / ERC** (correlation-aware) at the institutional tier.
- **Execution**: `cost(Δpos) = (fees+slippage)/1e4·|Δpos| + κ·Δpos²`. The linear term achieves
  **bit-for-bit parity** with P08's `LinearCostModel`/`reference_loop`; the quadratic term
  models convex impact (capacity: one large rebalance costs more than two small ones).

## Anti look-ahead & determinism
- Everything feeding the decision at `t` comes from P08's `GuardedView` (≤ t): a signal
  that reads the future **fails the run** (`LookAheadError`). Tested (`test_desk_lookahead`).
- Weighting vol uses **lagged** realized returns (`s_{t-1}·market[t]`).
- Desk state is reset at `t==0` → two runs on the same series match exactly.

## Reproducibility
MLflow run via `core.backtest.tracking.tracked_run`: params (weighting, costs, κ, signals,
`n_trials`, `simulated`) + **net and gross** metrics + per-signal contribution + net PnL
figure + git SHA + DVC version. Fixed seed (`SEED=42`). Snapshot in `results/last_run.json`.

## Run it
```bash
# Prerequisite: P08's Rust core compiled in the worktree
uv run maturin develop -m core/backtest/_loop/Cargo.toml --release

uv run pytest projects/10_portfolio_execution/tests   # 37 tests
uv run python projects/10_portfolio_execution/src/run_desk.py
```
> Warning: `pyproject.toml`'s `testpaths` points at the P01 foundation; run P10 tests via
> **explicit path** until convergence adds `projects/10_…/tests` (see CONVERGENCE.md).

## Status
Pipeline validated end-to-end on the **3 real signals** P02/P06/P09 (37 green tests,
`ruff`/`mypy core` clean, MLflow run logged). Net PnL is **negative** (−4.4654): the positive
gross on a mean-reverting synthetic series is an artifact (the signals track the generating
process), not alpha, and execution costs push it down further. Details and adversarial
verdict: [results/SYNTHESIS.md](results/SYNTHESIS.md),
[results/RISK_REVIEW.md](results/RISK_REVIEW.md). Next: [CONVERGENCE.md](CONVERGENCE.md).
