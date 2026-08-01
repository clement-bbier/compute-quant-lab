# Project 04 — Compute Index & Forward Curve

> LOCAL context. Global glossary and conventions: root CLAUDE.md. Detailed methodology
> and status: [README.md](README.md).

## Specific thesis
The price of compute has no deep history: build it. Construct (a) the canonical
compute spot index (Silicon Data / GPU Markets standard, CME futures settlement)
and (b) a SIMULATED forward curve for the announced-but-unlisted CME compute futures. Foundational
data product on which P03 (term structure) and P06 (derivatives) depend.

## Modules owned
- `core/ingestion/` (compute leg) · `infra/collectors/` · `projects/04_compute_index_curve/`.
- Forbidden: `core/pricing/` (P01), root protected zone. → convergence patches.

## Architecture (SOLID / configurable)
- **Sources**: `ComputeIndexSource` → `MarketplaceProxySource` (real, PoC), `SiliconDataSource` (canonical stub).
- **Aggregation**: `IndexEstimator` + `OutlierFilter` (Strategy) → `DEFAULT_INDEX_CONFIG` = market standard.
- **Forward**: `ForwardCurveModel` (Rust MC / Python oracle) + `ForwardCalibrator` (OLS AR(1) / half-life).
- Everything swappable via injection (`IndexConfig`, `build_forward_curve(...)`) without touching the core.

## Real/simulated boundary (non-negotiable)
`Curve.simulated` is required (no default). Forward = always simulated. Spot = real
(marketplace) or canonical (Silicon Data). Dedicated tests guarantee the invariant.

## Progress status
- [x] Types + protocols + aggregation strategies (trimmed mean 20% + 2.5 MAD, configurable)
- [x] Point-in-time `build_spot_index`, no carry-forward, anti look-ahead (tested)
- [x] Idempotent `CsvSnapshotStore` + rewritten collector (Vast.ai token-gated)
- [x] Schwartz forward: analytical Python oracle + MC, Rust engine (2% parity)
- [x] OLS AR(1) calibration (+ half-life fallback), MLflow orchestration
- [ ] Wire up Silicon Data (SDH100RT) — API spec + token
- [ ] Accumulate the real snapshot series (cron) then calibrate on the real index
- [ ] Promote the forward into `core/pricing/curve/` (convergence, after P01)

## Key results
End-to-end SIMULATED forward curve generated (Rust engine, OLS AR(1)), converging to spot
at τ=0 (2.808 $/GPU·h, real index on `data/snapshots`), replayable MLflow run (params + git
SHA). Committed artifact: [results/run_summary.json](results/run_summary.json). Details:
[README.md](README.md).
