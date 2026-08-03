# Backlog

Known gaps, parked deliberately. One line each, with the pointer that carries the
detail. Last reviewed: 2026-08-02.

| Item | Why it's parked | Reference |
|---|---|---|
| Bi-temporality of the GPU snapshot store | `snapshotted_at` is the only time axis; the energy store already has `publish_time` vs `interval_start`. Aligning the two is a schema migration, not a patch. | [ADR 007](decisions/007-provenance-and-point-in-time-in-the-cold-store.md) |
| Logging in the Streamlit dashboards | Both dashboards call `configure_logging()` at module top, but their data-loading paths log nothing — no boundary lines for a reader watching a live session. | rule `.claude/rules/observability.md` |
| `core/data_quality/` is an empty package | The `data-quality-auditor` agent and `/data-quality-check` skill both specify checks that have no implementation. Undecided: build them, or retire the agent + skill. | [CLAUDE.md §4](../CLAUDE.md) |
| `mypy` covers `core` only | `make lint` runs `mypy core`; `infra/` and `projects/` are unchecked, so a type error there reaches CI green. | `Makefile`, `pyproject.toml` |
| TensorDock venue is dormant | The connector is implemented and key-gated, but every live inventory pull so far returned an empty node list, so the venue contributes no observations. | `core/ingestion/providers/tensordock.py` |
| Showcase site | The design tokens in `dashboard_kit/tokens.py` are exported as a flat JSON-serialisable dict for a public site that does not exist yet. | `dashboard_kit/tokens.py` |
| Bare `except` in the MCP JSON serialiser | `pd.isna` raises on non-scalars; the `pass` is correct but silent, which the observability rule discourages. Documented in place rather than changed. | `infra/mcp-servers/gpu-price-server/service.py` |
| Historical thinning in the committed Parquet snapshot lake (`data/snapshots/`) | Before V8.1, `ParquetPriceStore`'s dedup key was `COLUMNS` only (no `region`/`provider_detail`): two distinct offers at the same instant/source/model/lease/price/availability but a different region or provider_detail silently collapsed to one row on every collector write since the lake was first populated. The key now includes the optional descriptive columns (fixed forward), but rows already dropped by prior writes cannot be recovered — the committed history predating this fix may undercount genuinely distinct offers. `region` is populated on 42,127/85,935 committed rows and `provider_detail` on 26,441/85,935 (2026-08-03 measurement), so the exposure is real, not theoretical; the scale of what was actually lost is not reconstructable from the data that remains. | `core/storage/parquet_store.py`, `core/storage/tests/test_idempotence.py::test_distinct_regions_same_price_are_not_deduplicated` |
