# Project 05 — Energy ↔ Compute Basis

> LOCAL context. Global glossary and conventions: root CLAUDE.md. Detailed methodology
> and status: [README.md](README.md). Cross-cutting decisions: [docs/decisions/](../../docs/decisions/).

## Project-specific thesis
The spark spread varies **by region**: regional electricity price (FR/DE, ENTSO-E) ×
local **PUE** × hardware efficiency. The inter-region **basis** (difference of regional
spreads, PUE-adjusted) opens a geographic arbitrage: place the GPU load where the spread
is widest. P05 measures this basis point-in-time, quantifies its dislocations and their
persistence, and honestly exposes its limitations.

## Modules owned
- `projects/05_energy_compute_basis/` only.
- Read-only: all of `core/` (P01 `core.pricing`, P04 `core.ingestion`, `core.utils`),
  root protected zone. Any need touching the protected zone → convergence process (`docs/parallel-ops.md`).

## Architecture (SOLID / DI)
- `RegionConfig` (PUE, FX, efficiency) = injected config, no magic numbers.
- `build_regional_pricer(cfg)` → `SparkSpreadPricer` (P01) **per region** (PUE lives in the
  `PowerModel`, hence one pricer per region).
- `BasisCalculator(pricers, reference=...)` **pure**: prices each region, aligns via inner
  join (point-in-time), `basis[r] = spread[r] − spread[reference]`.
- `detect_dislocations(basis)`: episodes where `|basis| > threshold` (p95 amplitude, fraction
  of time) + persistence = **AR(1) half-life** of mean reversion.
- I/O (ENTSO-E, P04 compute index, MLflow) isolated in `src/data.py` + `src/run_basis.py`;
  `src/basis.py` stays pure (no hidden I/O).

## Real / synthetic boundary (non-negotiable)
ENTSO-E FR/DE energy fallback order (V5.3): committed cold store (`data/cold/energy/`, real,
zero key required, label `entsoe_cold_store`) -> live ENTSO-E if a token is set (real, label
`entsoe`) -> labeled **deterministic synthetic fallback** (label `synthetic`). Compute index =
real (P04 marketplace) or labeled synthetic fallback. No simulated series is ever served as
real; the `energy_source` / `compute_source` label is logged in MLflow.

## Assumed risks (PoC)
Regional PUE = a strong, poorly observable assumption. Compute is often **global** → the
basis is mostly driven by energy × PUE (compute revenue cancels out between regions at
equal FX/compute prices). Transfer costs/latency ignored at PoC stage → don't over-interpret
a "free" arbitrage.

## Progress status
- [x] `RegionConfig` + `build_regional_pricer` (tests)
- [x] Point-in-time `BasisCalculator` (multi-region basis, PUE sensitivity, anti look-ahead)
- [x] `detect_dislocations` (threshold + AR(1) half-life)
- [x] `run_basis.py` orchestration + MLflow run + `results/SYNTHESIS.md`

## Out of scope (institutional tier)
Optimized load routing, transfer costs/latency, capacity constraints, executable
tradable inter-region signal.
