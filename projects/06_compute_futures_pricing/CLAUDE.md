# Project 06 — Compute Futures Pricing (theoretical)

> LOCAL context. Global glossary and conventions: root CLAUDE.md. Detailed methodology
> and launch instructions: [README.md](README.md). Cross-cutting decisions: [docs/decisions/](../../docs/decisions/).

## Project-specific thesis
Compute futures (CME, settling on the Silicon Data SDH100RT index) are
**announced but not listed** (regulatory review). P06 prices them **theoretically**:
cost-of-carry model `F = S·e^{(r−y)τ}`, base `F − S`, sensitivities (to r, y, τ),
using the real compute spot (P04) and the SIMULATED forward curve (P04, Schwartz).
Edge: be ready to value the base the day it lists.

## Modules owned
- `core/pricing/derivatives/` (new subpackage) · `projects/06_compute_futures_pricing/`.
- Off-limits: `core/pricing/__init__.py` and P01 files, root protected zone. → convergence patches.

## Architecture (SOLID / DI)
- **Contracts** (`derivatives/protocols.py`): `CarryModel` (forward source, `simulated`
  flag in the contract), `FuturesPricer` (orchestrator → `FuturesQuote`).
- **Core** (`derivatives/carry.py`): `carry_forward`, `implied_convenience_yield`
  (inverse), `carry_sensitivities`, `CostOfCarryModel`. Pure functions.
- **Quoting** (`derivatives/futures.py`): `FuturesQuote` (`simulated` MANDATORY),
  `CarryFuturesPricer` — **always** infers the implicit yield from the injected forward.
- **Adapter** (`src/p04_forward_adapter.py`, project layer): plugs the P04 Schwartz
  forward into `CarryModel` (years→days conversion), `simulated=True`.

## Real/simulated boundary (non-negotiable)
`FuturesQuote.simulated` is mandatory (no default), like P04's `Curve.simulated`.
All P06 output is `simulated=True`: futures are not listed. Spot = real (`core.ingestion`)
or a **logged** fallback assumption. Dedicated tests enforce the invariant (flag + consistency).

## Progress status (PoC-now)
- [x] Cost-of-carry core: forward, base, implied yield, sensitivities (pure, typed functions)
- [x] `FuturesQuote` with mandatory `simulated` flag + `CarryFuturesPricer` (DI)
- [x] P04 forward adapter (carry ↔ Schwartz consistency tested point by point)
- [x] `run_pricing.py` demo: real spot (logged fallback), term structure, reproducible MLflow run
- [ ] Wire in the real spot (accumulated snapshots) and calibrate the forward on the real index
- [ ] Institutional tier: multi-maturity surface, calendar spreads, options on futures

## Key results
End-to-end theoretical base generated over 4 maturities (exogenous carry + P04 forward),
implied yield extracted from the Schwartz forward, reproducible MLflow run (params + git SHA).
19 passing tests. Details: [README.md](README.md). WARNING: THEORETICAL/SIMULATED.
