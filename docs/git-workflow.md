# Lab parallel git workflow

> How several focused instances work in parallel without breaking `main`.
> This document describes the **branch and worktree lifecycle**; **module
> ownership** (who writes where) lives in
> [parallel-ops.md](parallel-ops.md), the single source of truth. Read both
> together: here the "how to merge", there the "who owns what".

## 1. Branch model

| Branch | Role | Rules |
|---|---|---|
| `main` | Protected, stable | Only receives reviewed merges, green CI. Never a direct commit, never a force-push. |
| `integration` | Convergence | Features merge here **first**. It is the base for every working branch. |
| `feature/PNN-<name>` | One per project/instance | Lives in its own worktree, branched off `integration`. |
| `chore/<topic>` | Infra maintenance | Same rules as `feature/*` (e.g. this orchestration setup). |

`PNN` = roster project id (e.g. `P01`, `P04`, `P08`). One focused instance =
one `feature/PNN-<name>` branch = one worktree = one owned module.

## 2. Worktrees: 1 worktree = 1 DISJOINT module

Each instance works in an isolated worktree, branched off `integration`:

```bash
git worktree add ../lab-PNN -b feature/PNN-<name> integration
```

The worktree writes **only** into the module it owns (see the ownership
partition table in [parallel-ops.md](parallel-ops.md)). To list / clean up:

```bash
git worktree list
git worktree remove ../lab-PNN      # once the feature is merged
```

## 3. Protected zone

`CLAUDE.md`, `.claude/`, `.mcp.json`, `pyproject.toml` only change through
the convergence session (the one driving `integration`), never from a
peripheral worktree. A worktree that needs to touch them prepares a patch
and hands it up to convergence. Otherwise: guaranteed merge conflicts on the
most shared files.

## 4. Anti-conflict discipline (before merging a feature)

```bash
# In the feature's worktree:
git fetch origin
git rebase origin/integration       # replay the feature on the up-to-date base
# rerun the tests: pytest && ruff check . && mypy core
git switch integration
git merge --no-ff feature/PNN-<name>  # or via PR
```

- **Rebase before merge**: the feature replays cleanly on an up-to-date `integration`.
- **Green tests required** after rebase, before merge.
- **`--no-ff`** (or PR): keeps an explicit trace of the merge point.

## 5. integration -> main

`integration` only promotes to `main` once **CI is green** and the **review
is done**. The merge is a **clean fast-forward** (no divergence):

```bash
git switch main
git merge --ff-only integration
```

## 6. Forbidden

- Never commit directly to `main`.
- Never force-push to `main` or `integration`.
- Never write outside your owned module from a worktree.
- Any push to a shared branch (`integration`, `main`) requires explicit
  confirmation from the research director.

## 7. Typical instance cycle

1. Convergence creates/keeps `integration` up to date with `main`.
2. The instance opens its worktree: `git worktree add ../lab-PNN -b feature/PNN-<name> integration`.
3. It works **only in its own module**, with semantic commits.
4. Before merging: `git fetch && git rebase origin/integration`, green tests.
5. Convergence merges `feature/PNN-<name>` -> `integration` (PR or `--no-ff`).
6. Once a milestone is reached and CI is green: `integration` -> `main` via `--ff-only`.

## 8. Worktrees — native Claude Code practices

> Distilled from the official "Run parallel sessions with worktrees" docs and
> 2026 usage feedback (links in section 9). The manual method in section 2
> remains the **lab standard** (base = `integration`, naming
> `feature/PNN-<name>`); what follows tools it and makes it ergonomic.

### Two ways to create a worktree

- **Manual (lab standard)** — explicit base and name, branched off
  `integration`, then **initialize the environment in each worktree** (fresh
  checkout):

  ```bash
  git worktree add ../lab-PNN -b feature/PNN-<name> integration
  cd ../lab-PNN && uv sync --extra dev
  ```

- **Native Claude Code (ad hoc / analysis)** — `claude --worktree <name>`
  creates a worktree under `.claude/worktrees/<name>/`. Warning: it branches
  from `origin/HEAD` (= `main`), **not** `integration`: reserve it for
  throwaway sessions (reading logs, queries). To start from local state, set
  `worktree.baseRef: "head"` in settings.

### Secret propagation (`.worktreeinclude`)

A worktree is a fresh checkout: `.env` (gitignored) is **not** there. The
`.worktreeinclude` file (`.gitignore` syntax) lists gitignored files to copy
automatically into each new worktree. **Essential here**: the connectors
(ENTSO-E, Silicon Data) need tokens. See [`.worktreeinclude`](../.worktreeinclude).

### Subagents in an isolated worktree

A lab employee can run in its own worktree by adding `isolation: worktree`
to its frontmatter (or "use a worktree for your agents"). Ideal for large
disjoint batches: each agent tests end to end then opens a PR.

### Clean test baseline (key practice)

Before handing a worktree to an instance: create it, run `pytest && ruff
check . && mypy core` **immediately**, confirm green. After the instance's
work, rerun the same suite: any new error is then **attributable** to the
instance, not to a pre-existing state.

### Staying oriented with many running sessions

Name the worktrees, shell aliases to jump between them, colored terminal
tabs, notifications enabled, and keep a dedicated "analysis" worktree for
logs / queries. The instance roster and prompts (see the note below) act as
a **shared task board**: each instance reads its owned module and writes
only there (anti-collision, see the partition in [parallel-ops.md](parallel-ops.md)).

> Note: this section used to point at `docs/orchestration/` for the roster
> and per-instance prompts. That directory has since been removed from the
> repository (see `docs/decisions/001-worktree-convergence-model.md`); the
> reference is kept here as a description of the practice, not as a live link.

### Cleanup

`git worktree list` for the inventory; `git worktree remove ../lab-PNN` once
the feature is merged (`--force` if there are uncommitted changes). Native
worktrees with no changes are swept automatically after `cleanupPeriodDays`.

## 9. Sources

- Claude Code — *Run parallel sessions with worktrees*: <https://code.claude.com/docs/en/worktrees>
- Claude Code — *Power user tips*: <https://support.claude.com/en/articles/14554000-claude-code-power-user-tips>
