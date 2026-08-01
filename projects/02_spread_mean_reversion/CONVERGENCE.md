# P02 -> Convergence

Patches touching the **protected zone** (`pyproject.toml`, `.claude/`, `core/`) or other modules:
prepared here, **not applied** in the P02 worktree. To be applied by the convergence session
(`integration` pilot).

---

## 1. Root `pyproject.toml`

### 1a. P02 tests discovered by pytest
`projects/02_spread_mean_reversion/tests/` is not in `testpaths` (P02 only writes to its own
module). Align with the convention already opened by P04.
```toml
[tool.pytest.ini_options]
testpaths = [
    "tests",
    "core/backtest/tests",
    "projects/04_compute_index_curve/tests",
    "projects/02_spread_mean_reversion/tests",
]
```
> In the meantime: run explicitly with `uv run pytest projects/02_spread_mean_reversion -q`.

---

## 2. ENTSO-E connector in `core/ingestion/` (generic energy leg)
The real energy leg is currently loaded from `projects/02_.../src/data_sources.py`
(`load_energy_entsoe`, direct call to `entsoe-py`). This is a **reusable** building block (P03, P06…
will need it): it belongs in `core/ingestion/`. Proposal:
- `core/ingestion/energy_market.py`: `EntsoeSource` (token `ENTSOE_API_TOKEN`), parsing -> EUR/MWh
  UTC tz-aware series, documented gap-filling (rule `data-integrity`).
- Version the real series as plain git (`data/raw/energy/…`) before any published backtest.

---

## 3. Silicon Data wiring (`core/ingestion/compute_index.py`)
`SiliconDataSource.fetch` raises `NotImplementedError`. For a backtest on a **deep real compute
history**, wire up the SDH100RT API (token `SILICONDATA_API_TOKEN` + endpoint). To be decided with P04
(owner of `core/ingestion` compute leg).

---

## 4. `references/` (owned by `feature/research`) — via `literature-scout`
Distill for the institutional tier (3b):
- Ornstein-Uhlenbeck / mean-reversion half-life (Avellaneda & Lee; Ernie Chan).
- Engle-Granger (1987), Johansen — critical values and out-of-sample stability.
- **Deflated Sharpe Ratio** (Bailey & Lopez de Prado): essential as soon as z-thresholds are scanned
  (`n_trials` is tracked in MLflow but no adjustment is applied yet).

---

## 5. Missing employee: `risk-validator` agent (lab growth, prompt §8)
The root `CLAUDE.md` §6 describes `risk-validator` (adversary) but it is **not registered** in
the environment (verified: absent from the agent list). The `/backtest-pitfalls` audit for P02 was
therefore done manually. To be created via `agent-architect` / `/new-agent` (written to `.claude/agents/`,
protected zone -> convergence). Proposed spec: read-only adversary, hunts look-ahead /
overfitting / data-snooping / unrealistic costs, refuses to trust any Sharpe > 2 without deflated
Sharpe + walk-forward. Same for `infra-engineer` (also absent).

## 6. Candidate rule `.claude/rules/` (optional)
A path-scoped rule `projects/**/strategy*.py` reminding: "every strategy implements P08's
`Strategy` Protocol and only accesses `view.history()`/`view.latest()` (<= t)". Ties in
with the existing `quant-no-lookahead` rule.
