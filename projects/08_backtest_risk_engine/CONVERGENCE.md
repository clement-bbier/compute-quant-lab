# P08 → Convergence

Patches touching the **protected zone** (`pyproject.toml`, `.claude/`, `core/utils/`) or
other modules: prepared here, **not applied** in the P08 worktree. To be applied by the
convergence session (pilot `integration`).

---

## 1. `pyproject.toml` (root)

### 1a. P08 tests discovered by pytest
`core/backtest/tests/` is not under `tests/` (P08 only writes inside its own module).
```toml
[tool.pytest.ini_options]
testpaths = ["tests", "core/backtest/tests"]
```

### 1b. Rust core build (MANDATORY loop)
The `core/backtest/_loop/` subcrate is self-contained (maturin). The engine hard-imports
the compiled `backtest_loop` module, so it must be installed in the environment.
```toml
[project.optional-dependencies]
dev = ["pytest>=8.0", "ruff>=0.4", "mypy>=1.10", "pre-commit>=3.7", "maturin>=1.7"]
```
Install step (dev + CI), after `uv sync --extra dev`:
```bash
uv run maturin develop -m core/backtest/_loop/Cargo.toml
```
> CI: add an "install Rust toolchain (stable) + maturin develop" step **before**
> `pytest`/`mypy`, otherwise the engine import fails. `core/backtest/_loop/target/` is
> gitignored (build artifacts), `Cargo.lock` is committed (reproducible build).

### 1c. (optional) tooling exclusions
```toml
[tool.ruff]
extend-exclude = ["core/backtest/_loop/target"]
```

---

## 2. Rule candidate `.claude/rules/backtest-mlflow-logging.md`
Path-scoped to `core/backtest/**` + `projects/**`. To be created via `agent-architect` / `/new-agent`.

> # Backtest reproducibility
> - Every backtest MUST log an MLflow run containing: params, metrics, **git SHA**
>   and **DVC version** of the data. Use `core.backtest.tracking.tracked_run`.
> - No strategy metric gets published without a replayable MLflow run (`run_id`).
> - Track the number of trials (`n_trials`) for multiple testing (deflated Sharpe at the
>   institutional tier). Ties in with `backtest-runner` (execution) and
>   `risk-validator` (adversary).

---

## 3. `core/utils/tracking.py` (neighboring module, not owned)
Move the DVC versioning logic (currently in `core/backtest/tracking.py`) upstream, so
that the **whole** lab inherits it, and pick a non-deprecated MLflow backend.
- Add the `dvc_version` tag to `core.utils.tracking.run` (cf. `dvc_version()` in P08).
- **MLflow 3.14** puts the file-store in *maintenance mode*: it raises without
  `MLFLOW_ALLOW_FILE_STORE=true` (current workaround in `run_demo.py`). Decide at the
  lab scale: file-store opt-out **or** `sqlite:///…` backend. Align with the root
  CLAUDE.md's "experiments/" convention (relocate the tracking URI out of `projects/08`).

---

## 4. `references/` (owned by `feature/research`) — via `literature-scout`
Distill for the institutional tier 3b:
- Bailey & López de Prado — *Deflated Sharpe Ratio*, *The Probability of Backtest Overfitting*.
- López de Prado — purged k-fold + embargo (anti train/test temporal leakage).

---

## 5. Divergence to reconcile: Rust integration P01 ↔ P08
- **P01**: Rust core as **fallback** (`skipif(_kernel is None)`, Python oracle by default).
- **P08**: Rust core **mandatory** (hard import, no runtime fallback).
Pick a single lab-wide convention (probably: mandatory in CI, fallback for quick dev).

---

## 6. Inherited gap (flagged by P01): `core.utils`
`core.utils.logging` and `core.utils.config` are missing. P08 worked around this via DI
(no `print`, no hardcoded path). To be created under `core/utils/` to standardize
logging/config.
