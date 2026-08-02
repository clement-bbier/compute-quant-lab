# Storage roadmap — from file to real time

> **Status: Phases 0-1 delivered** (`core/storage/` — `ParquetSnapshotStore` +
> DuckDB query layer, see [`core/storage/results/SYNTHESIS.md`](../core/storage/results/SYNTHESIS.md)).
> Phases 2-5 below remain roadmap, not yet built.
>
> How the lab stores data to **train models on a reliable history** today,
> and **serve real time** tomorrow — without over-building. Guiding rule:
> *the right storage depends on the usage*, and we only move to the next
> phase when a concrete **trigger** justifies it.

## 0. Non-negotiable principle: reproducibility first

Training **always** reads the **versioned cold store** (Parquet, tracked as
plain git files), **never** the mutable hot store (TimescaleDB/Redis). An
MLflow run logs the **git SHA** of the code (already wired into
`core.utils.tracking`) -> since the data lives in the same git history, that
SHA already pins the exact dataset version, so a run can be retrained
identically months later. The hot store serves **serving/monitoring**, not
reproducibility.

```
   COLLECT -> COLD (Parquet, plain git, immutable, point-in-time) -> training / backtest
                  |_(stream)_> HOT (Timescale/Redis) ─────────────> live serving / dashboard
```

## 1. Current data reality (starting point)

| Leg | Cadence | History | Current storage |
|---|---|---|---|
| Energy (ENTSO-E) | hourly, batch | deep (API) | `data/raw/` (local cache, gitignored by design) |
| Compute (Vast/RunPod) | snapshot (live) | **none -> we accumulate it** | `data/snapshots/*.csv` |
| Compute forward | simulated | -- | project artefacts |

-> Everything is **batch**. Real time only makes sense once a stream exists (Phase 2).

## 2. Abstraction layer (to lay down BEFORE any backend)

A `core/storage/` package with **Protocols** (DI/SOLID), so projects depend
on abstractions, never on a concrete backend (same pattern as the P04 sources):

- `PriceStore`: `write(frame)`, `read(query, as_of)` -> Parquet impl, then Timescale.
- `TickStream`: `produce(tick)`, `consume()` -> Redpanda impl (Phase 2).
- `HotCache`: `set_latest(...)`, `get_latest(...)` -> Redis impl (Phase 4).

**Benefit**: switching backend = new implementation, **zero change** to
strategies/models (OCP). Migrating between phases becomes painless.

## 3. The phases (each with its own trigger)

### Phase 0 — Cold store: **Parquet, plain git** *(delivered — `core/storage/`)*
- Replace `CsvSnapshotStore` with **`ParquetSnapshotStore`**: columnar, typed,
  compressed, partitioned (`source` / month). Append-only, idempotent (dedup kept).
- **Track** `data/snapshots/` in git as plain files -> every dataset versioned
  through normal git history. `data/raw/`, `data/interim/`, and `data/cold/`
  stay local, gitignored caches by design (see the ADR 005 addendum) — only
  `data/snapshots/` is plain-git-tracked.
- **Quality fix** along the way: keep the **distribution** of offers per
  model (do not reduce to 1 row/model) — aggregation (trimmed mean) belongs
  to the P04 index, not to the store.
- **Trigger**: this is the foundation, no prerequisite. **Owner**: `data-engineer`.

### Phase 1 — Query layer: **DuckDB** *(delivered — `core/storage/duckdb_query.py`)*
- DuckDB reads the Parquet **directly in SQL**, embedded, **zero server**.
- Usage: EDA, point-in-time joins at scale, feature building (P07/P09).
- **Trigger**: pandas-on-files becomes painful, or analytical SQL is needed.
- **Owner**: `data-engineer`. Near-zero cost.

### Phase 2 — Real-time ingestion: **Redpanda** + tick collector *(the real pivot)*
- Turn the daily snapshot into a **high-frequency tick collector**: poll
  Vast/RunPod every 1-5 min -> publish to a `compute.prices` topic (Redpanda,
  Kafka-compatible, single binary, lighter than Kafka), via **local
  docker-compose**.
- Consumers: (a) **cold** sink (Parquet/plain git, training), (b) **hot**
  sink (Phase 3), (c) **Redis** update (Phase 4). GPU price **moves
  intraday** -> streaming makes sense.
- **Trigger**: you want intraday granularity / a live pipeline.
- **Owner**: `infra-engineer` (services/compose/CI) + `data-engineer` (schemas/sinks).

### Phase 3 — Historical hot store: **TimescaleDB** (default) / ClickHouse *(at volume)*
- TimescaleDB = Postgres + time series (hypertables, **continuous
  aggregates**, compression). SQL, transactional, rich ecosystem -> **recommended default**.
- Stores the streamed ticks for fast time-range queries + continuous
  aggregates (1 min / 1 h OHLC of the compute index).
- ClickHouse **only** for massive OLAP (>>10^8 rows, heavy analytical scans).
- **Trigger**: query latency on Parquet/DuckDB starts to hurt, or aggregates on a live stream.
- **Owner**: `infra-engineer`.

### Phase 4 — Serving / hot features: **Redis** *(once a live consumer exists)*
- Redis holds the **latest price / feature** (+ short windows) to serve at
  **low latency**: live spark spread pricer, P09 inference, P10 desk, dashboard.
- **Trigger**: a model/dashboard needs sub-second current state.
- **Owner**: `infra-engineer`.

### Phase 5 — Point-in-time feature store *(once ML matures)*
- Split offline (training, cold) / online (serving, hot), **point-in-time correct**.
- Promote the features from `core/features/` (P07) here. Avoid premature
  work: the point-in-time joins (already done by P07) are the core; the
  tooling comes after.

## 4. Anti-over-engineering (read before deploying Kafka)

- **Do not** stand up Redpanda + Timescale + Redis **on top of daily
  snapshots**: that would be a race engine with no fuel. Streaming only
  makes sense **after** deciding to tick intraday (Phase 2).
- Stay at **Phase 0-1** as long as the data is batch and the volume modest
  (DuckDB-on-Parquet absorbs a lot). **Local-first**: everything in
  docker-compose; managed cloud only at the institutional tier.
- **Lay down the abstraction (section 2) now**: that is what makes phases
  2-4 painless when the day comes.

## 5. How this gets built (lab ritual)

A dedicated batch = a data-infra project, run in a **worktree** like any
other (plan -> tests-first -> commit -> convergence). Owned modules:
`core/storage/` + `infra/`. Owners: `infra-engineer` (to be built via
`agent-architect`) + `data-engineer`.

**Recommended next concrete step: Phase 2** (Redpanda tick collector) — Phases
0-1 are delivered; Phase 2 is the next trigger-justified move, once intraday
granularity or a live pipeline is actually needed.
