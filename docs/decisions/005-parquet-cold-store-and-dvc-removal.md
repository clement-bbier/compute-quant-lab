# 5. Parquet cold store, and dropping DVC in favor of plain git / git-lfs

## Status
Accepted — 2026-06

## Context
The original data-versioning plan was DVC: `data/cold/ercot.dvc` and
`data/interim/aligned_spark.parquet.dvc` pointer files, with the real content
in a DVC cache/remote. In practice `.dvc/config` had no remote configured, so
`dvc pull` failed for anyone without the original author's local DVC cache —
the pointers were unrecoverable by a fresh clone. Separately, `core/storage/`
(the P11 promotion of storage code out of a numbered `projects/` folder, see
[003](003-projects-numeric-prefix-debt.md)) needed a queryable, typed,
point-in-time-capable store for GPU snapshot data richer than the original
6-column CSV, which the CSV-based `SnapshotStore` could not represent without
silently dropping columns.

## Decision
- Introduce `core/storage/` as a Parquet-based cold store
  (`ParquetPriceStore`, `EnergyColdStore`) with a DuckDB query layer
  (`duckdb_query.py`) for point-in-time joins, deduplicating on full row
  content (not just `(t, source, model, lease)`) so that multiple offers
  sharing a timestamp are preserved rather than collapsed into one arbitrary
  row.
- Replace DVC entirely: data is versioned as plain git-tracked files
  (git-lfs for large binary artifacts). `dvc pull` and the `.dvc` pointer
  files are removed; `data/raw/` remains a local, gitignored cache by design
  (never meant to be committed, real or synthetic) rather than a DVC-tracked
  path.
- `data/cold/` (ERCOT) and `data/interim/aligned_spark.parquet` move to
  direct git/git-lfs tracking.

## Consequences
- A fresh `git clone` is now sufficient to obtain versioned data — no DVC
  install, no remote configuration, no unrecoverable pointer files.
- Any code still computing a `dvc_version` tag (there were, at one point, two
  divergent implementations — a sha256 of `dvc.lock` and a sha1 of all
  `.dvc` files) needs reconciling around a git-commit-based version tag
  instead; DVC is no longer a dependency anywhere in the tree.
- The provider registry's row-level dedup (this decision) versus the index
  layer's aggregation responsibility (collapsing same-timestamp offers into a
  single `VenueRate` per source) is a deliberate split: the store preserves
  the full observed distribution, `build_spot_index` is where aggregation
  belongs.
