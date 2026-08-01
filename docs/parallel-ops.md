# Parallel operations — the "research factory" model

How to run many agents, worktrees and terminals in parallel without
collapsing into merge conflicts.

## The three lanes

| Lane | Mechanism | Parallelism | Output |
|---|---|---|---|
| **Collection** | subagent swarm (`/market-scan`) | high (~10) | syntheses -> `references/` |
| **Construction** | git worktrees + sessions | moderate | code -> integration branch |
| **Convergence** | 1 pilot session | sequential | review, merge, update `CLAUDE.md` |

Collection: "many agents" is safe, they only return syntheses.
Construction: the risk is git, not Claude -> partition rule below.
Convergence: the real bottleneck is human -> reconciliation cadence.

## Golden rule of worktrees: 1 worktree = 1 DISJOINT module

Each parallel session owns exactly one directory and writes only into it.
Ownership partition (avoids merge collisions):

| Worktree / branch | Owns (writes only here) |
|---|---|
| `feature/ingestion` | `core/ingestion/`, `infra/mcp-servers/`, `infra/collectors/` |
| `feature/data-quality` | `core/data_quality/` |
| `feature/features` | `core/features/` |
| `feature/models` | `core/models/` |
| `feature/backtest` | `core/backtest/` |
| `feature/dashboard` | `projects/01_digital_spark_spread/` |
| `feature/research` | `references/` |

### Protected zone (do NOT modify from a peripheral worktree)
`CLAUDE.md`, `.claude/`, `.mcp.json`, `pyproject.toml` change rarely and go
through the convergence session ONLY. Otherwise, conflicts are guaranteed.

## Guardrails inherited automatically
Hooks and rules live in the committed `.claude/`: every worktree and every
session inherits the write-block on `data/raw/`, auto-formatting, and the
anti-look-ahead rules. You can parallelize without worrying about data integrity.

## Suggested cadence
1. Launch a `/market-scan` (collection lane) -> feeds `references/`.
2. Open 2-4 worktrees on disjoint modules (construction lane).
3. Once per cycle, the pilot session merges the branches into `integration`,
   reruns the tests, updates the `CLAUDE.md` index, reconciles the syntheses.

## Monitoring sessions
`claude agents` opens the sessions view (running / blocked / done),
useful when many terminals are running.
