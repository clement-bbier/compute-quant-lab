# Project 08 — Backtest & Risk Engine

> LOCAL context. The glossary and global conventions live in the root CLAUDE.md.

## Specific thesis
The lab's trust foundation: a **point-in-time, reproducible, polyglot** backtest engine
with an **anti-look-ahead guard** that *fails* as soon as a signal at t consumes data > t.
Every strategy project (P02, P09, P10…) plugs into it. It makes the convention "every
backtest logged to MLflow + git SHA" executable.

## Architecture (two phases)
1. **Phase 1 (Python, guarded)**: at each t, `GuardedView(data, t)` → `strategy.signal()`
   → position array. The look-ahead guard lives here (tested red).
2. **Phase 2 (Rust, optional fast path)**: `backtest_loop.accumulate(positions, prices, fees, slippage)`
   → PnL / returns / turnover / trades over the long history. Pure Python oracle =
   `core/backtest/reference_loop.py` (bit-exact parity, tested fallback used
   automatically when the compiled crate isn't available).

## Reproducibility
Every run logs to MLflow: params + metrics (PnL, Sharpe, max DD, turnover, hit ratio)
+ git SHA + PnL figure. Determinism guaranteed (seed logged, fixed order).

## Progress status (PoC-now done)
- [x] Risk metrics (annualized Sharpe, max drawdown, turnover, hit ratio)
- [x] Look-ahead guard (red test: a strategy cheating via `at(t+1)` makes the run fail)
- [x] Cost model (fees + slippage) injected
- [x] Rust accumulation loop + bit-exact parity with the Python oracle
- [x] Two-phase engine + MLflow tracking (params + metrics + git SHA + figure)
- [x] Reproducible demo on synthetic fixtures

## Key results
Demo (`run_demo.py`, mean-reversion z-score on a synthetic series, 512 obs, fees 10 bps
+ slippage 5 bps) — reproducible MLflow run, artifact committed in
[results/SYNTHESIS.md](results/SYNTHESIS.md):
- Total PnL ≈ 0.115 · **Sharpe ≈ 0.62** (realistic, no overfitting red flag) · max DD ≈ -4.7%
- turnover ≈ 93.7 · hit ratio ≈ 0.47
- 35 passed, 3 skipped (analytical metrics, red-guard, determinism, costs, Rust/Python parity;
  skips are Rust-kernel-only tests when the crate isn't built).

**Limitations / pitfalls covered**: look-ahead (active guard + red test), explicit costs,
determinism (fixed seed + summation order), reproducibility (git SHA + data version).
**Out of scope (tier 3b)**: deflated Sharpe (only `n_trials` is tracked), purged/embargoed CV,
multi-asset, fine-grained execution modeling.

## Convergence
Protected-zone patches (Rust CI wiring, `testpaths`): see
`docs/decisions/002-per-project-ci-testpaths-gap.md`.
