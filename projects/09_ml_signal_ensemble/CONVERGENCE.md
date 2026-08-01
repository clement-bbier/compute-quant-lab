# P09 → Convergence

Patches touching the **protected zone** (`pyproject.toml`, `.claude/`, `core/` outside
`core/models/`) or other modules: prepared here, **not applied** in the P09 worktree.
To be applied by the convergence session (pilot `integration`).

---

## 1. `pyproject.toml` (root) — test discovery by pytest

`core/models/` (owned by P09) and its tests aren't in `testpaths`, nor is the P09 project.
Align with the convention already opened by P04/P02.

```toml
[tool.pytest.ini_options]
testpaths = [
    "tests",
    "core/backtest/tests",
    "core/models/tests",                       # <- P09 (model layer)
    "projects/04_compute_index_curve/tests",
    "projects/02_spread_mean_reversion/tests",
    "projects/09_ml_signal_ensemble/tests",    # <- P09 (project)
]
```

> In the meantime: `uv run pytest core/models/tests projects/09_ml_signal_ensemble -q`.
> Warning: CI runs each folder **in isolation** (conftest collision between projects).
> The `core/models/tests` tests **import `core.backtest`** → they require the compiled
> Rust core (`maturin develop -m core/backtest/_loop/Cargo.toml`), as already documented
> for P05/P08.

---

## 2. Promoting building blocks into `core/features/` (lab growth, prompt §8)

- The causal transforms derived from the spread (`SpreadFeatureSpec` / `FeaturePipeline._spread_features`
  in `core/models/pipeline.py`) overlap with the exogenous transforms in `core/features` (`lag_feature`,
  `rolling_mean_feature`, `diff_feature`). To be **unified** into `core.features` for a single
  source of truth for point-in-time feature engineering (P03/P07/P09).
- `InMemoryExogenousSource` (in `projects/09_.../src/synthetic.py`) is a reference implementation
  of the `ExogenousSource` protocol: a candidate for `core/features` (useful to any ML/test project).

---

## 3. Missing hire: `risk-validator` agent (lab growth, prompt §8 — MANDATORY)

The root `CLAUDE.md` §6 describes `risk-validator` (adversary) and the P09 prompt makes it
**mandatory** before trusting any Sharpe, but it is **still not registered** in the
environment (already flagged by P02). The P09 `/backtest-pitfalls` audit was therefore
conducted **by hand** ([results/SYNTHESIS.md](results/SYNTHESIS.md)). To be created via
`agent-architect` / `/new-agent` (written to `.claude/agents/`, protected zone → convergence).
Proposed spec: **read-only** adversary, hunts look-ahead / overfitting / data-snooping /
unrealistic costs; rejects any Sharpe that's "too good" without a **deflated Sharpe**
(with a real `n_trials`) + **walk-forward**; requires MLflow reproducibility.

---

## 4. `references/` (owned by `feature/research`) — via `literature-scout`

Distill for the institutional tier (3b), P09's theoretical foundation:
- **López de Prado**, *Advances in Financial Machine Learning*: purged k-fold + embargo,
  **Deflated Sharpe Ratio**, backtest overfitting (PBO), robust feature importance (MDA/MDI).
- **Bailey & López de Prado (2014)**, *The Deflated Sharpe Ratio*.
- Sequential: LSTM / **Temporal Fusion Transformer** (Lim et al.) for the upper tier.

---

## 5. Integration note (not a patch, a reminder)

`core/models/` has a read dependency on `core.pricing` (P01), `core.features` (P07),
`core.backtest` (P08) — all assumed present in `integration`. `core.models.strategy`
deliberately imports `core.backtest.protocols` (not the `core.backtest` package) where
possible, but `core.backtest`'s `__init__` still gets pulled in as soon as the engine is
touched → **Rust core required** at backtest runtime.
