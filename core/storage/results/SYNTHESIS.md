# P11 — storage_layer · synthesis

**Branch**: `feature/P11-storage_layer` (base `integration`). **Scope**: Phase 0+1 of
`docs/storage-roadmap.md` — reproducible cold store, abstraction layer, DuckDB query.
**Out of scope**: real time (Phases 2-4, documented, not coded).

## What is delivered (`core/storage/`)
- **`protocols.py`** — `PriceStore` (DI/SOLID Protocol) + documented stubs `TickStream`
  (Redpanda, Phase 2) / `HotCache` (Redis, Phase 4). The abstraction is laid down *before*
  any backend -> painless migration between phases (OCP).
- **`schema.py`** — canonical schema of the lake + `normalize_frame` (UTC tz-aware
  **mandatory**, `float64` price, `int64` availability). A naive timestamp is **rejected**
  (point-in-time integrity).
- **`parquet_store.py`** — `ParquetPriceStore`: Parquet lake **partitioned by `source` /
  month**, append-only, **idempotent on row content** (preserves the distribution of
  offers), `read(as_of=t)` **point-in-time** (anti look-ahead).
- **`duckdb_query.py`** — `query(sql, store)`: embedded SQL (zero server) over the lake,
  `prices` view; handles the empty lake (schema without rows).
- **`migrate.py`** — `migrate_csv_snapshots`: CSV (P04) to Parquet switchover, lossless,
  idempotent.
- **`converters.py`** — `snapshots_to_frame`: the single *read* coupling point with
  `core.ingestion`.
- **`demo.py`** — consumer run: DuckDB EDA + **DVC version logging**
  (`core.utils.tracking`) -> repro.
- **`infra/collectors/gpu_price_snapshot.py`** — **dual write** rewire: CSV (P04, unchanged)
  + Parquet (cold store). Idempotent; injectable `fetch` (network-free tests).

## Tests — `pytest core/storage/tests`: **40 passed**
| Family | File | Guarantee |
|---|---|---|
| (a) round-trip | `test_parquet_roundtrip.py` | types, source/month partition, **distribution preserved**, `PriceStore` conformance, naive rejection |
| (b) idempotence | `test_idempotence.py` | re-append = no-op; distinct offers kept |
| (c) point-in-time | `test_point_in_time.py` | `read(as_of=t)` ⊆ `{snapshotted_at ≤ t}`, source filter, naive `as_of` rejection |
| (d) DuckDB | `test_duckdb_query.py` | SQL over the lake (aggregates), empty lake |
| (e) migration | `test_migrate.py` | CSV to Parquet preserves the rows, idempotent |
| rewire | `test_collector_rewire.py` | dual write, Parquet idempotence |
| consumer run | `test_demo.py` | DuckDB stats (pure, without MLflow) |

Method: **strict TDD** — every behavior had its test fail before implementation.
Deterministic fixtures, **zero network**.

## Exit gate
- [x] `ruff check .` — All checks passed.
- [x] `mypy core` — clean (the initial crash was a stale `.mypy_cache`, purged).
- [x] `pytest core/storage/tests` — 23 passed.
- [x] Synthesis + convergence handoffs (later applied; see `docs/decisions/005-parquet-cold-store-and-dvc-removal.md`).
- [x] **`data/snapshots/` as versioned Parquet**: *live* seed was blocked at the time this
  synthesis was written (no `.env` in the worktree, no `VASTAI/RUNPOD` token, reading the
  main `.env` refused by the credentials guardrail). **No data was fabricated**. Data is now
  versioned as plain git / git-lfs, not DVC — see
  `docs/decisions/005-parquet-cold-store-and-dvc-removal.md`.
- [x] Nothing written outside `core/storage/` + `infra/collectors/` (+ the `data/snapshots/`
  artifact). Neither merge nor push.

## Environment note
`duckdb 1.5.4` was installed **ad hoc** in the venv at the time (now a formal `pyproject`
dependency). `mlflow` absent from this interpreter -> the full MLflow run of `demo.main`
executes in the lab's `uv` env; the attached `run_summary.json` reflects an **empty** lake
(0 rows), honest before seeding.
