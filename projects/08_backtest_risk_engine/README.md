# P08 — Backtest & Risk Engine

The lab's trust foundation: a **point-in-time, reproducible, two-phase**
backtest engine with an **anti-look-ahead guard** that fails as soon as a
signal at `t` consumes data beyond `t`. Every strategy project (P02, P09,
P10, …) plugs into it.

## Architecture (two phases)
1. **Phase 1 (Python, guarded)** — at each `t`, `GuardedView(data, t)` feeds
   `strategy.signal()`, producing a position array. The look-ahead guard
   lives here, tested red (a strategy peeking at `t+1` makes the run fail).
2. **Phase 2 (Rust, optional fast path)** — `backtest_loop.accumulate(positions,
   prices, fees, slippage)` accumulates PnL / returns / turnover / trades
   over the full history. A pure Python oracle
   (`core/backtest/reference_loop.py`) is the tested fallback, bit-exact
   parity, used automatically when the compiled crate isn't available.

## Modules
| Path | Role |
|---|---|
| `core/backtest/engine.py` | Two-phase orchestration; imports the compiled `backtest_loop` when available, else the tested Python fallback (`core/backtest/reference_loop.py`) — see `core/backtest/_loop/README.md`. |
| `core/backtest/guards.py` | `GuardedView`, the look-ahead guard (rejects negative indices to block numpy wrap-around). |
| `core/backtest/metrics.py` | Sharpe (annualized), max drawdown, turnover, hit ratio. |
| `core/backtest/costs.py` | Fee + slippage cost model, injected. |
| `core/backtest/tracking.py` | MLflow run logging (params, metrics, git SHA). |
| `src/demo_fixtures.py` | Deterministic synthetic fixture (seed=42, 512 observations) used by the demo below. |
| `run_demo.py` | End-to-end demo: `ZScoreMeanReversion` strategy over the fixture → MLflow run → `results/SYNTHESIS.md`. |

## Run

```bash
uv sync --extra dev
uv run maturin develop -m core/backtest/_loop/Cargo.toml

uv run pytest core/backtest/tests projects/08_backtest_risk_engine/tests -q
uv run python projects/08_backtest_risk_engine/run_demo.py
mlflow ui --backend-store-uri experiments/mlruns
```

## Results (demo, synthetic fixture)
`ZScoreMeanReversion` (window=32, z_scale=2.0), fees 10bps + slippage 5bps,
`n_trials=1` (no hyperparameter search). Full detail:
[results/SYNTHESIS.md](results/SYNTHESIS.md).

| Metric | Value |
|---|---:|
| Total PnL (capital=1) | 0.1150 |
| Sharpe (annualized) | 0.6154 |
| Max drawdown | -0.0468 |
| Turnover | 93.686 |
| Hit ratio | 0.4746 |

**Reading**: not an alpha claim — P08 is the engine, not a candidate
strategy. The point of this demo is to prove the pipeline (look-ahead guard
+ costs + Rust core + MLflow tracking) runs end to end with reproducible
metrics. A modest Sharpe (0.62) on a synthetic mean-reversion setup is not
suspicious, unlike a very high one (see P02's `/backtest-pitfalls` verdict).

## Reproducibility
Fixed seed (42), fixed summation order on the Rust side, bit-exact parity
with the Python oracle. Every run logs params + metrics + git SHA to MLflow
via `core.utils.tracking`.

## Limitations / out of scope
Deflated Sharpe (only `n_trials` is tracked, not yet applied), purged/embargoed
cross-validation, multi-asset backtests, fine-grained execution modeling —
tier-3b items, not implemented here. `core.backtest` treats the compiled Rust
kernel as an optional fast path, falling back to the tested Python oracle
when the crate isn't built (`import core.backtest` never requires
`maturin develop`) — see
[docs/decisions/002-per-project-ci-testpaths-gap.md](../../docs/decisions/002-per-project-ci-testpaths-gap.md)
for the related CI wiring gap.
