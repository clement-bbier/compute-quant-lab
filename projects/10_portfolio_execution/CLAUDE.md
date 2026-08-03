# Project 10 — Portfolio & Execution (Desk layer)

> LOCAL context. Root glossary and conventions: root CLAUDE.md. Detailed methodology
> and status: [README.md](README.md). Cross-cutting decisions: [docs/decisions/](../../docs/decisions/).

## Project-specific thesis
Turn **signals** (mean-reversion P02, derivatives P06, ML P09) into a desk-quality
**portfolio**: weighting under a **risk budget**, a realistic **execution/cost model**,
**net PnL**. This is the layer that answers "how much do we put on, and what's left after fees."

## Decoupling (key to parallelism)
P10 does NOT depend on the internals of P02/P06/P09: it consumes **generic signals** via
the `Strategy`/`PointInTimeView` abstraction from **P08** (`core.backtest`). The **mocked**
(in-memory) producers remain for regression tests; the **real** P02/P06/P09 producers
(promoted into `core.signals`, P12) are wired in without changing the desk's code (OCP).

## Owned modules
- `projects/10_portfolio_execution/` only.
- Read-only: `core.backtest` (P08: engine, look-ahead guard, metrics, tracking).
- Off-limits: any `core/`, root protected zone → convergence process (`docs/parallel-ops.md`).

## Architecture (SOLID / DI)
- `src/provenance.py` — `SignalProvenance(name, simulated)`: the `simulated` flag is
  **mandatory** (rule `forward-real-simulated`). A test fails if it's missing.
- `src/signals.py` — `SignalProducer` Protocol + deterministic mocks (`ConstantMock`,
  `MeanReversionMock`, `MomentumMock`) — placeholders for P02/P06/P09, bounded [-1, 1], point-in-time.
- `src/portfolio.py` — **inverse-vol** weighting (`inverse_vol_weights`) behind a
  `WeightScheme` abstraction (OCP seam → `ERCScheme` risk-parity at the institutional stage);
  `PortfolioConstructor`: floored vols + gross-leverage clipping → net position.
- `src/execution.py` — `ExecutionModel`: **linear + quadratic impact** costs `κ·Δpos²`
  (return space, P08 convention); linear term matches `LinearCostModel` exactly.
- `src/desk.py` — `DeskStrategy`: composite `Strategy` injected into P08; blends N signals
  into a net position, estimates realized vol **point-in-time**, records per-signal attribution.
- `src/run_desk.py` — desk pipeline → P08 backtest (gross) → costs → net PnL → MLflow run.

## Real/simulated boundary (non-negotiable)
The 3 signals are the **real** P02/P06/P09 producers (`simulated` inherited from each); the
desk price series, however, remains **synthetic and labeled** (`simulated=True`). No PnL is
ever sold as alpha (see [results/RISK_REVIEW.md](results/RISK_REVIEW.md)).

## Progress (PoC-now)
- [x] Inverse-vol weighting + risk budget + ERC seam (OCP), vol floor, gross cap
- [x] Linear + quadratic impact execution model, oracle parity with P08
- [x] Composite `DeskStrategy` anti look-ahead (P08 guard), determinism, exact attribution
- [x] Reproducible MLflow run (params + **net AND gross** metrics + git SHA + net PnL figure)
- [x] 42 green tests; `ruff`/`mypy core` clean
- [x] **Real signals** P02/P06/P09 promoted into `core.signals` (P12), wired via `REAL_PRODUCERS`
- [ ] `risk-validator` agent (missing, protected zone)
- [ ] Institutional tier: constrained risk-parity optimizer, capacity, desk limits, live execution

## Key results
Pipeline validated end-to-end on the **3 real signals** P02/P06/P09 + **simulated** desk series.
**Net** PnL **−4.4654** vs **gross** **+0.5057**: with a turnover of 455, costs (fees+slippage+
impact κ=0.02) don't just eat into the loss, they **blow it up** — a direct illustration of
"execution costs are the PnL killer" (§10). Net Sharpe −7.12, t-stat **−16.55** on n_obs=1,500,
95% CI [−7.96, −6.28]: unlike P02/P09's near-zero Sharpes, this one is **statistically
distinguishable from zero — decisively negative**, not just noisy. The positive gross on a
mean-reverting synthetic series is an artifact (the signals track the generating process), not
alpha. No alpha is claimed: see [results/SYNTHESIS.md](results/SYNTHESIS.md) and the
adversarial verdict in [results/RISK_REVIEW.md](results/RISK_REVIEW.md).
