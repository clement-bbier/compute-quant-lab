# 1. Parallel worktrees with a protected zone and a convergence session

## Status
Accepted — 2026-06

## Context
Research on this lab runs as several independent project instances (P01-P10,
P13, P14) developed in parallel, each in its own git worktree branched off
`integration`. Left unconstrained, parallel instances editing shared files
(`pyproject.toml`, CI config, `.claude/`, root `CLAUDE.md`) would collide on
every merge.

Each instance recorded any change it needed to make outside its own module in
a `CONVERGENCE.md` file at its module root, rather than making the change
itself.

## Decision
- Define a **protected zone** (`pyproject.toml`, `.github/`, `.mcp.json`,
  `.claude/`, root `CLAUDE.md`) that peripheral worktrees never modify.
- Each worktree owns exactly one disjoint module (see the ownership partition
  in `docs/parallel-ops.md`) and writes only there.
- A single **convergence session** (the one driving `integration`) is the only
  place that touches the protected zone, applying the patches each instance
  queued in its `CONVERGENCE.md`.
- `integration` promotes to `main` only via fast-forward, once CI is green.

## Consequences
- Merge conflicts on shared files are structurally avoided during parallel
  waves; the cost is deferred, batched integration work in the convergence
  session.
- `CONVERGENCE.md` files accumulate real technical debt items (CI wiring,
  dependency additions, promotions to `core/`) that must be tracked to
  completion instead of being forgotten once a project's worktree merges.
  Some were applied (e.g. `duckdb`, `pyarrow`, `mcp` moved into main
  dependencies; DVC replaced by git-lfs); others were not (see
  [002](002-per-project-ci-testpaths-gap.md)). The `CONVERGENCE.md` files
  themselves have been retired in favor of this `docs/decisions/` ADR log —
  they described a process, not a durable decision, and were not being kept
  in sync with what actually landed.
