# P10 — Patches for the convergence session

> P10 only writes to `projects/10_portfolio_execution/`. Changes to the **protected
> zone** (`pyproject.toml`, `.claude/`, root `CLAUDE.md`, `.mcp.json`, `core/`) are
> listed here and applied **only** by the session driving `integration`.

## 1. `pyproject.toml` — collect P10 tests
Project tests are not collected by default (`testpaths = ["tests"]`). Add an isolated CI
job for `projects/10_portfolio_execution/tests` (same pattern as other projects: each
directory run separately because of bare-import `conftest` files). Example CI command:
```bash
uv run pytest projects/10_portfolio_execution/tests
```

## 2. Wire in the real P02/P06/P09 signals
Replace the mocks (`signals.py`) with adapters behind the **same** `SignalProducer`
Protocol (`name`, `provenance`, `signal(view) -> float ∈ [-1, 1]`):
- **P02** (mean-reversion) → adapter for the hysteresis z-score (already a P08 `Strategy`).
- **P06** (futures/derivatives) → directional view of the implied carry/yield.
- **P09** (ML) → model output normalized to [-1, 1].
No changes expected in `desk.py`/`portfolio.py`/`execution.py` (that's the point of the decoupling).
Update `provenance.simulated=False` when the signal is real and its underlying data is real.

## 3. `risk-validator` agent (missing from the roster)
The lab plans for this **adversary** (root CLAUDE.md §6) but the agent doesn't exist yet in
`.claude/agents/` (a gap shared with P02). To be created during convergence via `agent-architect`. Its
mandate on P10: **attack the aggregated net PnL** (not the gross) — correlations between signals
ignored by inverse-vol, underestimated costs, composite overconfidence (see RISK_REVIEW.md §5).

## 4. Institutional tier (backlog, not PoC)
- `WeightScheme` → implement `ERCScheme` (correlation-aware risk-parity, point-in-time
  covariance). The seam is already in place (`portfolio.py::ERCScheme` raises `NotImplementedError`).
- If the optimizer becomes generic and reusable → promote it into `core/` (PoC → foundation
  principle), via convergence.
- Capacity / desk limits / live execution; deflated Sharpe and walk-forward on real signals.

## 5. Reference (optional)
Delegate to `literature-scout` a review (risk parity / ERC, Almgren-Chriss impact models,
robust portfolio construction) → `references/` (module owned by `feature/research`).
