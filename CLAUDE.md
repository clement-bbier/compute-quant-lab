# Compute Quant Lab

> Lab index. Keep this file **< 200 lines**: it's a map pointing to the
> rules / skills / agents, not an encyclopedia.

## 1. Research thesis

**Compute** (GPU rental: Nvidia H100/Hopper, Blackwell) is a new asset class
whose raw material is **electricity**. The lab models, prices, and arbitrages
the spread between the two — the *digital spark spread* — to produce signals
tradable by a Global Markets-style desk.

Guiding principle: **PoC → foundation**. Any reusable building block from a
project moves up into `core/`. Project N+1 starts with project N's infra
already in place.

## 2. Glossary

- **Spark spread**: margin = compute revenue − energy cost of production.
- **PUE** (Power Usage Effectiveness): ratio of total datacenter draw / IT draw.
- **Point-in-time**: only use data *known at instant t* (anti look-ahead).
- **Alpha**: excess return unexplained by market exposure.
- **Marginal cost of compute**: energy cost of one GPU-hour.

## 3. Data source registry

| Source | Flow | Access | Status |
|---|---|---|---|
| ENTSO-E Transparency | FR/DE electricity spot price (€/MWh) | `entsoe-py`; cold store committed (`data/cold/energy/`, zero key), API token for live refresh only | implemented, cold store committed |
| EPEX Spot | Day-ahead price | Paid API / proxy | to investigate |
| GPU marketplaces (Vast.ai, RunPod, PrimeIntellect, DataCrunch, Cudo, Hyperstack, TensorDock) | GPU rental price (€/h) | Public APIs, self-historized via `core/ingestion/providers/` | implemented, live validation per-venue (see [docs/decisions/004](docs/decisions/004-provider-registry-architecture.md)) |
| ERCOT (GridStatus.io) | Real-time market price, grid stress | API token | implemented (P07 branch), real data |
| Gas/weather markets | Exogenous variables | API | backlog (synthetic fallback in place) |
| S&P Global / Kensho | Reference financial data | MCP (connected) | available |
| Tavily | Web research (scanning) | MCP (connected) | available |

> Implementation details: `core/ingestion/`. Tokens: `.env` (never committed).
> ⚠️ There's no historical price for compute: `infra/collectors/gpu_price_snapshot.py`
> accumulates it day by day into `data/snapshots/`. The energy leg, by contrast, has deep history.

## 4. Repo structure

- `core/` — shared installable library (`pip install -e .`)
  - `ingestion/` connectors (`providers/` = the GPU marketplace registry) · `data_quality/` declared but unimplemented (see note below) · `pricing/` spark spread + derivatives
  - `features/` point-in-time feature engineering · `models/` XGBoost, purged-CV, deflated Sharpe
  - `backtest/` engine + metrics · `storage/` Parquet cold store + DuckDB query layer · `signals/` reusable signal producers · `utils/` config, logging, tracking (MLflow)
- `data/` — `snapshots/` (raw collected, **git-versioned**) → `interim/` → `processed/`; `cold/` = typed Parquet lake (ERCOT)
- `dashboard_kit/` — shared design tokens + dark theme for every Streamlit dashboard (`.streamlit/config.toml` mirrors its palette)
- `experiments/` — MLflow runs (local tracking, no server)
- `projects/NN_name/` — a standalone research project (has its own CLAUDE.md); the numeric prefix is deliberate debt, see [docs/decisions/003](docs/decisions/003-projects-numeric-prefix-debt.md)
- `infra/mcp-servers/` — **code** for custom MCP servers (≠ root `.mcp.json`)
- `infra/collectors/` — scheduled services (GPU price snapshot, ERCOT backfill)
- `tests/` — pytest (root/P01 suite; every other module's tests run in isolation, see [docs/decisions/002](docs/decisions/002-per-project-ci-testpaths-gap.md))
- `references/` — knowledge layer: `bibliography.md` + distilled notes (`energy-markets/`, `ml-finance-pitfalls/`, `stat-arb/`)
- `docs/decisions/` — ADR log for cross-cutting architectural decisions (see §7)

> ⚠️ `core/data_quality/` is referenced by the `data-quality-auditor` agent and the
> `/data-quality-check` skill but contains no logic yet (empty package). Undecided:
> implement the gap/outlier/point-in-time checks the skill already specifies, or retire
> the agent + skill + references. Flagging here rather than silently picking one.

## 5. Orchestration mechanisms (`.claude/`)

- **rules/** — path-scoped constraints, auto-loaded on the paths they declare:
  `python-quality`, `data-integrity`, `quant-no-lookahead`, `observability` (logging
  policy), `forward-real-simulated` (the real/simulated boundary),
  `training-cold-store`, `backtest-mlflow-logging`
- **skills/** — procedures: `/run-backtest`, `/data-quality-check`, `/new-research-project`, `/new-agent`
  - **knowledge layer**: `/cointegration-analysis`, `/spread-trading-playbook`, `/backtest-pitfalls`
  - **parallel scanning**: `/market-scan` (swarm of subagents on the compute market)
- **agents/** — the lab's "staff" (see §6)
- **settings.json** — deterministic hooks (auto-format, blocks writes to `data/raw/`, blocks `.env`)

## 6. The lab's staff (subagents)

The main session = research director who delegates. Each agent runs in
isolation and returns only a synthesis.

- `agent-architect` — meta-agent: builds/revises the lab's other agents, skills, rules, hooks
- `data-engineer` — ingestion, scraping, connectors
- `data-quality-auditor` — gaps, outliers, point-in-time integrity (see the `core/data_quality/` note in §4)
- `quant-researcher` — features, modeling, signals
- `backtest-runner` — isolated execution → PnL / Sharpe / drawdown
- `risk-validator` — **adversary**: hunts look-ahead, overfitting, data snooping
- `infra-engineer` — MCP servers, CI, environment
- `literature-scout` — arXiv / SSRN scanning
- `code-reviewer` — quality, typing, conventions

## 7. Parallel operations (research factory)

Massively parallel work along 3 tracks: **collection** (subagent swarm via
`/market-scan`), **construction** (git worktrees, 1 worktree = 1 disjoint module),
**convergence** (1 pilot session that merges and reconciles). Golden rule: a worktree
only writes to its own module; the protected zone (`CLAUDE.md`, `.claude/`, `.mcp.json`,
`pyproject.toml`) is touched only by the convergence session.
→ Details and ownership partition: `docs/parallel-ops.md`. Helper: `scripts/new-worktree.ps1`
(branches off `integration`, see `docs/git-workflow.md`).

Structural decisions that came out of past convergence sessions are recorded as ADRs in
`docs/decisions/` (worktree/convergence model, the provider registry architecture, the
Parquet cold store migration, the real/simulated type invariant, and known open gaps
like per-project CI wiring) — read there before re-deciding something already settled.

## 8. Conventions

- Python 3.12 (pinned via `.python-version`), environment managed via **uv** (`uv sync`), committed lockfile.
- All data I/O goes through `core/` — never a hardcoded path in a project.
- `data/raw/` is **immutable**: never write into it by hand (PreToolUse hook).
- Every backtest is logged to MLflow with params + metrics + git SHA.
- Semantic commits. Tests + ruff green before merge (pre-commit + CI).

## 9. Useful commands

```bash
uv sync                 # install the environment from the lockfile
pytest                  # run the tests
ruff check . && mypy core   # quality
mlflow ui               # experiment dashboard (local)
```
