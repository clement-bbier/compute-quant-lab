# 2. Per-project test suites are not wired into the default pytest run

## Status
Accepted (known gap, not yet closed) — 2026-06

## Context
`pyproject.toml`'s `[tool.pytest.ini_options].testpaths` lists only `tests`
(the root suite for `core.pricing`, P01). Nine of the eleven project
instances (P02, P03, P05, P06, P07, P08, P09, P10, plus `core/ingestion/
providers`, `core/storage`, and the `gpu-price` MCP server) each queued a
`CONVERGENCE.md` patch to add their own test directory to `testpaths`, on the
grounds that a bare `pytest -q` at the repo root silently skips them.

Convergence deliberately did **not** apply these patches as a single merged
`testpaths` list. The reason recorded across the handoffs: `conftest.py`
files in disjoint project directories collide when pytest collects several
`projects/*/tests` folders in the same session (bare-name imports fighting
over the same module name). The interim workaround adopted everywhere was to
run each folder in isolation:
```bash
uv run pytest projects/02_spread_mean_reversion -q
uv run pytest core/ingestion/providers/tests -q
# ...
```

## Decision
Keep `testpaths = ["tests"]` as the default. Each module's tests are run
explicitly, in isolation, one directory per invocation — in CI as a matrix of
isolated steps, not a single merged `pytest` call.

## Consequences
- A bare `uv run pytest` at the repo root does **not** exercise most of the
  codebase; this is expected, not a regression to fix by editing
  `testpaths`.
- `Makefile`'s `TEST_DIRS` (not `.github/workflows/ci.yml`, which just calls
  `make test`) must enumerate every test directory explicitly (guarding each
  with `[ -d "$d" ] || continue` so an unmatched glob doesn't leak a literal
  path into pytest's argv) — verify this list against the actual
  `projects/*/tests` and `core/*/tests` directories before trusting a green
  CI run as full coverage.
- Fixing the root cause (the numbered `projects/NN_name/` prefix isn't an
  importable package, forcing `sys.path.insert` and bare-name `conftest`
  collisions) is tracked as accepted architectural debt, not scheduled —
  see [003](003-projects-numeric-prefix-debt.md).
