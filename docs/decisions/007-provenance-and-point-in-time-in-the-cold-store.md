# 7. `simulated` as a store-level column, `EnergyColdStore.read(as_of=)`, and the remaining uni-temporal gap

## Status
Accepted — 2026-08

## Context
ADR 006 made `simulated: bool` a mandatory, no-default field on every type
carrying a forward/simulated *value* (`Curve`, `FuturesQuote`, ...). It did
not reach the compute ingestion leg: `Snapshot` and the Parquet/CSV stores had
no `simulated` column at all — the invariant was declared but not carried by
the schema the hourly collector actually writes. Separately, `EnergyColdStore`
already carried `publish_time` (the point-in-time anchor for forecast
vintages) but `read()` ignored it, returning the whole lake regardless of
`as_of` — so a backtest replaying instant `t` could see a forecast vintage
published after `t`, a live look-ahead channel the guard in
`core.backtest.guards` cannot see (it operates on already-materialized
arrays, not on the lake read that produced them). Neither store had an
`ingested_at` column distinguishing "when the price was observed"
(`snapshotted_at` / `interval_start`) from "when the row entered the lake."

The delicate part: the GPU snapshot store is a **monthly CSV, append-only,
written every hour by CI** (`infra/collectors/gpu_price_snapshot.py`). Adding
a mandatory column to `Snapshot` means the very next scheduled run appends to
a file whose on-disk header predates that column — `CsvSnapshotStore.append`
used `csv.DictWriter(..., extrasaction="ignore")` against whatever header the
existing file happened to have, which would have silently discarded
`simulated` for the rest of that calendar month.

## Decision
- **Schema**: `Snapshot` (`core/ingestion/protocols.py`) gains `simulated:
  bool` as a mandatory, **keyword-only** field with no default
  (`field(kw_only=True)`), not a plain trailing field — the class has several
  already-defaulted positional fields (`lease_type`, `availability`, the
  descriptive fields) before it, and a bare no-default field after them would
  be a `TypeError` at class-definition time. `kw_only=True` makes it
  mandatory without reordering or breaking any existing positional call. A
  red-first test (`test_snapshot_construction_fails_without_simulated`)
  pins the omission as a `TypeError`. Every real venue connector (Vast.ai,
  RunPod, PrimeIntellect, CUDO, Hyperstack, TensorDock, DataCrunch) passes
  `simulated=False` explicitly — there is no synthetic compute-price fallback
  in this lab today, so `True` never appears at a real call site.
- **Cold store schema** (`core/storage/schema.py`, `core/storage/energy_store.py`):
  `SIMULATED` and `INGESTED_AT` join `OPTIONAL_COLUMNS` as a new
  `PROVENANCE_COLUMNS` group — tolerated-absent like the descriptive columns,
  but with a *documented* backfill value each, not a generic "unknown":
  - `simulated` absent -> backfilled `False`. Every row ever written by these
    stores came from a real collector run (there is no synthetic compute or
    energy fallback wired in production); this is a provenance fact about
    collector history, not a guessed default.
  - `ingested_at` absent -> backfilled `NaT` ("unknown ingestion time" is
    honest; a fabricated timestamp would not be).
- **CSV legacy compat (the delicate part), decision 2a — read**: rows/files
  predating `simulated` decode via a `False`-if-absent fallback in
  `CsvSnapshotStore.load`, same rationale as the store-level backfill.
- **CSV legacy compat, decision 2b — append/write**: unlike the purely
  optional descriptive columns (which a legacy header may keep lacking
  forever — enriching hardware metadata retroactively is not this store's
  job), `simulated` must never be silently dropped once every `Snapshot` you
  can construct always carries it. `CsvSnapshotStore.append` now checks the
  on-disk header before writing and, if it lacks `simulated`,
  rewrites **only the header line** of that file in place
  (`_ensure_header_has`) before appending the new row — an O(1) operation
  independent of the file's row count. Existing data rows are left exactly as
  they were (now "short" relative to the new header, not corrupted); they are
  backfilled on the next `load()`, per decision 2a. This was chosen over
  rolling to a new file suffix on mismatch: one file per month stays the
  contract, and the header rewrite is bounded and reversible (it is still
  valid CSV before and after). `test_append_to_legacy_file_keeps_its_header_layout`
  is the test that exercises exactly the code path the CI collector was going
  to hit within the hour this shipped; it is a **reinforcement** of a
  pre-existing test of the same name (which only asserted layout was not
  misaligned), not a relaxation — it now also asserts the header gains
  `simulated` and both the legacy and new rows report their correct
  provenance afterward.
- **Energy point-in-time**: `EnergyColdStore.read(as_of=...)` filters on
  `publish_time <= as_of` (inclusive boundary — a row published exactly at
  `as_of` was known at `as_of`). `as_of=None` (default) returns everything,
  unchanged from pre-existing behaviour — full backward compatibility for
  every current caller. `ParquetPriceStore.read(as_of=...)` already existed
  (filtering on `snapshotted_at`); the energy store's `as_of` is the same
  contract applied to its own point-in-time axis (`publish_time`, not
  `interval_start`).
- **`ingested_at` is forward-only, not bi-temporal**: both stores stamp it at
  write time (`pd.Timestamp.now(tz="UTC")`), inside the store, never accepted
  from the caller's frame (a caller-supplied value in the input frame is
  silently overwritten — this is intentional: the store, not the writer, owns
  "when this row entered the lake"). There is deliberately **no query axis**
  over `ingested_at` (no `as_of_ingestion` parameter, no way to reconstruct
  "what the lake looked like as of ingestion instant X"). Building that would
  require bi-temporal storage (a second point-in-time dimension queried
  independently of `publish_time`/`snapshotted_at`), which is out of scope
  here — this ADR only closes the gap between "the column exists" and "the
  column is silently dropped," not the larger bi-temporal-store question.

## Consequences
- The real/simulated invariant (ADR 006) now reaches the compute ingestion
  leg end-to-end: schema, CSV store, Parquet store, energy store. A future
  synthetic compute-price fallback (if the lab ever adds one, e.g. for gap-
  filling) has a column to write `simulated=True` into, rather than needing a
  second schema migration.
- The GPU snapshot store's uni-temporal limitation is **not** resolved by
  this ADR: `ParquetPriceStore.read(as_of=...)` filters on `snapshotted_at`
  only, same as before. There is still no way to ask "what did the lake look
  like as of ingestion instant X" for the GPU leg — only "what prices were
  observed by instant X," which is the axis that mattered for the backtests
  this store serves today. If a future project needs to replay exactly what a
  point-in-time backtest would have seen with the collector's actual cadence
  (not just the observation timestamps), that is a distinct bi-temporal
  storage decision, not covered here.
- `core.backtest.guards.LookAheadError` and
  `core.features.builders.LookAheadError` now both log at `ERROR` before
  raising (observability rule: a look-ahead raise is a failed operation, not
  a recoverable fallback) — brought into parity, still deliberately
  decoupled modules (no cross-import), per the existing "deliberate parallel"
  docstring already in `guards.py`.
- Every consumer that reads the lake (dashboards, `projects/*`) keeps its
  existing assertions unchanged: `normalize_frame`/`normalize_energy_frame`
  backward compatibility guarantees this, and the full test suite is green
  without touching a single pre-existing assertion in a consuming project.
