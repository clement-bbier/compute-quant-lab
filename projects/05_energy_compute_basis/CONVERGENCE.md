# Convergence patches — P05

> The protected zone (`pyproject.toml`, root `CLAUDE.md`, `.claude/`, `.mcp.json`) is
> only ever modified via the convergence session (see `docs/git-workflow.md` §3). P05
> prepares the patches here to be applied upstream; it does not apply them itself.

## 1. `pyproject.toml` — P05 test discovery (REQUIRED)

P05's tests live under `projects/05_energy_compute_basis/tests/` but are not collected
by a bare `pytest` invocation until they appear in `testpaths` (same pattern as P04).
Patch to apply at convergence:

```toml
[tool.pytest.ini_options]
testpaths = [
    "tests",
    "core/backtest/tests",
    "projects/04_compute_index_curve/tests",
    "projects/05_energy_compute_basis/tests",   # ← P05 addition
]
```

Until the merge, run explicitly: `pytest projects/05_energy_compute_basis -q`.

## 2. Building the Rust kernels in the worktree (ENVIRONMENT, not a source patch)

The full baseline requires the compiled Rust extensions (otherwise `core/backtest` raises
`ModuleNotFoundError: backtest_loop`). Prepare each worktree with:

```bash
uv run maturin develop -m core/backtest/_loop/Cargo.toml
uv run maturin develop -m core/pricing/_kernel/Cargo.toml
uv run maturin develop -m projects/04_compute_index_curve/forward_engine/Cargo.toml
```

No `core/` source is modified (gitignored `target/` outputs, installed into the venv).
