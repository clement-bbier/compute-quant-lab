# P11 — storage_layer · convergence handoffs

> This batch writes **only** into `core/storage/` + `infra/collectors/` (+ the
> `data/snapshots/` artifact). Everything touching the **protected zone**
> (`pyproject.toml`, `.claude/`) or the **P04 `core/ingestion/`** module is listed here for
> the convergence session — it is **not** applied in this worktree.

## 1. Dependencies & config (`pyproject.toml`)
- Add to `dependencies`: **`duckdb>=1.0`**, **`pyarrow>=15`** (the cold store and the query
  layer depend on them). `pyarrow` was already pulled in transitively by `pandas`;
  `duckdb` was installed **ad hoc** in the worktree venv (`pip install duckdb`) — to be
  made official in the lockfile (`uv add duckdb pyarrow`).
- Include the module's tests in CI: add **`core/storage/tests`** to `testpaths` (or to the
  CI matrix that runs each folder in isolation, see the `pyproject` pytest section note).
- **Pre-existing stub (P04)**: `mypy` 1.20 flags `core/ingestion/gpu_market.py` (`import
  requests`, `[import-untyped]`, not silenced by `ignore_missing_imports`). Add
  **`types-requests`** to the `dev` deps (installed ad hoc here for a green `mypy core`).
  Unrelated to P11.

## 2. Distribution fix (P04 — `core/ingestion/`)  ⚠️ do NOT edit here
- **Observation**: `parse_vastai_offers` emits **one row per offer** (N distinct H100 prices
  at the same instant). The dedup key of `CsvSnapshotStore` `(t, source, model, lease)`
  **collapses them into a single row** -> the intra-source distribution is destroyed *inside
  the store*, whereas aggregation belongs to the index (Silicon Data standard).
- **Delivered by P11**: `ParquetPriceStore` deduplicates on the **full row content** (price +
  availability included) -> **keeps the distribution** of offers, remains a faithful journal
  of observations.
- **To do at convergence**: adapt `build_spot_index` / `MarketplaceProxySource` to
  **aggregate the intra-source distribution** into a `VenueRate` (trimmed mean per source)
  **before** the `latest_by_source`. Today, on offers sharing a timestamp,
  `latest_by_source` would keep **an arbitrary offer** (last iterated) — incorrect as soon
  as the store preserves the distribution. The store now supplies the raw material; the
  index must do the aggregation.

## 3. Repoint the index at the Parquet cold store (P04)  ⚠️ do NOT edit here
- `MarketplaceProxySource.fetch` currently reads `CsvSnapshotStore.load()`. Wire it to the
  Parquet cold store: either `ParquetPriceStore(...).read(as_of=...)`, or a DuckDB query
  (`core.storage.duckdb_query.query`) for point-in-time joins at scale.
- Benefit: typed/columnar reads, native point-in-time (`as_of`), DVC-versioned.

## 4. Real seed + DVC tracking of the cold store  ⛔ blocked in this worktree
- **Director's decision**: *real seed via the live collector*. **Not executable here**: this
  worktree has **no `.env`** (created via `git worktree add`, which does not honor
  `.worktreeinclude`) and no `VASTAI_API_KEY` / `RUNPOD_API_KEY` key in the environment;
  reading the main `.env` is (correctly) refused by the credentials guardrail. No data was
  fabricated (real/simulated rule).
- **To be run in an environment with tokens** (convergence or a machine with `.env`):
  ```bash
  # 1) live reading -> dual write CSV (P04) + Parquet (cold store)
  python -m infra.collectors.gpu_price_snapshot
  # 2) version the produced Parquet lake (*.parquet.dvc pointers, see .gitignore)
  dvc add data/snapshots/**/*.parquet      # or: dvc add data/snapshots
  git add data/snapshots/**/*.dvc data/.gitignore
  # 3) consumer run (logs the DVC version via MLflow) — repro
  python -m core.storage.demo
  ```
- The layer is ready: as soon as data exists, `ParquetPriceStore` partitions it and DuckDB
  queries it; `core.utils.tracking` logs the DVC version.

## 5. New employee — `infra-engineer` persona (to register via `agent-architect` / `/new-agent`)
> Described here (the `.claude/agents/` zone is protected). To be materialized at convergence.

- **name**: `infra-engineer`
- **description**: "The lab's scheduled services, storage and CI: collectors (GPU price
  snapshot), Parquet/DVC cold store, DuckDB query layer, and — institutional phases —
  docker-compose Redpanda/TimescaleDB/Redis. To be called to set up/maintain the data
  infrastructure."
- **tools**: `Read, Write, Edit, Bash` (build/test/dvc/compose) — no application network.
- **system prompt (sketch)**: owns `core/storage/` + `infra/`; respects 1 worktree = 1
  module; never touches the protected zone (escalates a convergence patch); tests-first;
  immutable, DVC-versioned cold store; **local-first** (docker-compose), managed cloud only
  at the institutional tier; brings up Redpanda/Timescale/Redis **only after** the decision
  to tick intraday (anti-over-engineering, roadmap section 4).

## 6. Skill / rule candidate
- **Rule** (path-scoped to models/training): "training **always** reads the versioned cold
  store (`core.storage`), **never** the hot store (Timescale/Redis)". Materializes the
  non-negotiable principle of `docs/storage-roadmap.md` section 0. To be added under
  `.claude/rules/` at convergence.
