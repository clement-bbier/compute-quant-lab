# 4. GPU marketplace connectors as a pluggable provider registry

## Status
Accepted — 2026-06

## Context
The lab needs spot-price data from multiple GPU rental marketplaces
(Vast.ai, RunPod, then PrimeIntellect, DataCrunch, Cudo, Hyperstack,
TensorDock). The first wave (Vast.ai + RunPod) was implemented directly in
`core/ingestion/gpu_market.py`. Adding five more venues one at a time, each
in its own parallel worktree, required a shape that let every venue land
without touching any other venue's file.

## Decision
- `core/ingestion/providers/` hosts one module per venue: a pure
  `parse_<venue>` function, a token-gated `fetch_<venue>` I/O function, and a
  `<Venue>Provider` class (`name`, `required_env`, `fetch(now)`), all reusing
  a shared `base.normalize_gpu_model` helper.
- A `PROVIDERS` tuple in `providers/__init__.py` registers every venue; a key
  becoming available in the environment (`.env` / GitHub Secrets) activates
  its provider automatically — no other layer changes.
- `core/ingestion/gpu_market.py` becomes a backward-compatible shim
  re-exporting the original Vast.ai/RunPod symbols and delegating
  `fetch_live_gpu_prices` to `providers.fetch_all`, so the always-on
  collector (`infra/collectors/gpu_price_snapshot.py`) and GitHub Actions
  cron needed no changes.
- Each venue's parser was built and unit-tested against samples reconstructed
  from public API documentation, not a live call (the parallel worktrees have
  no `.env`). Confidence per venue is uneven as a direct result: high for
  PrimeIntellect and DataCrunch (stable, well-documented schemas), medium for
  Cudo and Hyperstack, lowest for TensorDock (ambiguous list-vs-mapping
  envelope). Live validation against the real APIs happens once secrets are
  available, not at parser-authoring time.

## Consequences
- Adding a venue is a 3-step, single-file change (see
  `core/ingestion/providers/__init__.py`), which is what made 5 venues
  addable in parallel, one per worktree, with zero merge collisions.
- PrimeIntellect aggregates other providers under the hood, so its
  `source=primeintellect:<provider>` values can double-count a venue that is
  also wired in directly (e.g. `primeintellect:datacrunch` overlapping the
  direct `datacrunch` venue). **RESOLVED**: `prefer_direct_venues`
  (`core/ingestion/compute_index.py:61`) drops aggregator quotes for venues
  also connected directly; `IndexConfig.prefer_direct` defaults to `True`
  (`compute_index.py:107`) and is applied on the active index-building path
  before outlier filtering (`compute_index.py:196`).
- Confidence level per venue (high/medium/low, see the provider docstrings)
  should be treated as a live caveat on data quality, not just implementation
  history, until each has been confirmed against a real API response.
