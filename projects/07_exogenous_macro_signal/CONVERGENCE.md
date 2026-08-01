# P07 → Convergence

Patches touching the **protected zone** (`pyproject.toml`, `.claude/`, `.gitignore`,
root `CLAUDE.md`) or unowned modules: prepared here, **not applied**
in the P07 worktree. To be applied by the convergence session (`integration` pilot).
P07 only wrote to `core/features/` + `projects/07_exogenous_macro_signal/`.

---

## 1. `pyproject.toml` (root) — P07 tests discovered by pytest
P07 tests live in owned modules (not under `tests/`). The global gate
`pytest -q` does not collect them until `testpaths` includes them (same case as P08 §1a).
```toml
[tool.pytest.ini_options]
testpaths = [
    "tests",
    "core/backtest/tests",
    "projects/04_compute_index_curve/tests",
    "core/features/tests",                       # <- P07
    "projects/07_exogenous_macro_signal/tests",  # <- P07
]
```
> In the meantime, P07 explicitly runs
> `pytest core/features/tests projects/07_exogenous_macro_signal/tests`.

## 2. `.gitignore` (root) — DVC pointers for raw exogenous data (RESOLVED, obsolete)
History: `dvc add data/raw/exogenous/*.parquet` used to succeed (cache populated, `.dvc`
files created), but the `data/raw/*` pattern also gitignored the `.dvc` pointers, preventing
their commit (same blocker as P01 §3). **Resolved differently**: DVC was removed from the
repo; `data/raw/` remains a local cache gitignored by design (never meant to be committed,
real or synthetic), so this blocker no longer applies.

## 3. Baseline tests: Rust kernels to compile (inherited from P08 §1b)
The global suite does not collect in a fresh worktree until `backtest_loop` (P08)
and `_kernel` (P01) are compiled. Before `pytest -q`, P07 had to run:
```bash
uv run maturin develop -m core/backtest/_loop/Cargo.toml
uv run maturin develop -m core/pricing/_kernel/Cargo.toml
uv run maturin develop -m projects/04_compute_index_curve/forward_engine/Cargo.toml
```
> Confirms the need (already flagged by P08) for a "maturin develop" step in CI **before**
> `pytest`/`mypy`. P07 adds no Rust crate (features are 100% Python).

## 4. Source registry (root `CLAUDE.md` §3) — gas / weather
Move "Gas/weather markets" from *backlog* to *in progress (P07, synthetic)* and record
the need for a **real connector** (day-ahead gas price, HDD/CDD weather) — falls to
`data-engineer`. Tokens → `.env` + `.worktreeinclude` (var `EXOGENOUS_API_TOKEN`, read by
`projects/07/src/sources.py`, currently a logged deterministic synthetic fallback).

## 5. `core/utils/` — promote UTC normalization (owner: core/utils)
`core.features.builders._to_utc_index` **duplicates** `core.pricing._timeindex.to_utc_index`
(integrity rule "UTC tz-aware, never naive"). Should be promoted to `core.utils` (e.g.
`core.utils.timeindex.to_utc_index`) so pricing, features, and future modules share
a single tested boundary.

## 6. User contribution — `DEFAULT_PUBLICATION_LAGS`
The default publication-lag table (`core/features/builders.py`) is **set by the
research director** (conservative values + per-variable justification). When wiring up
the real connector (item §4), recalibrate each lag against the **actual** publication
calendar (business day, timezone, revision delay) and, if the source exposes vintages,
feed the vintage frames directly (revision path already handled by `as_of_snapshot`).

## 7. New hires / references (lab growth, prompt §8)
- `risk-validator`: attack each feature (residual look-ahead, spurious correlation,
  data snooping on the thin real-compute history).
- `literature-scout`: energy drivers (gas, weather, HDD/CDD) and datacenter buildout → `references/`.

## 8. DoD status (prompt §11)
- [x] Green tests: anti-look-ahead (lag, red-first guard), alignment/timezone, revisions, builders — 16 + 4.
- [x] `ruff check .` & `mypy core` green.
- [x] MLflow run logged (params + lags + SHA); raw exogenous data in local cache (`data/raw/`, gitignored by design, cf. §2).
- [x] Synthesis `results/SYNTHESIS.md` + `run_summary.json` (lead, predictive power, pitfalls).
- [x] Nothing written outside `core/features/` + `projects/07_…` (aside from git-ignored data/MLflow artifacts). Branch committed, no merge or push.
