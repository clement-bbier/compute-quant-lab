# P05 — Energy ↔ compute basis synthesis

- Regions: FR, DE (reference = DE)
- Window: 2025-01-01 00:00:00+00:00 → 2025-01-31 23:00:00+00:00 (UTC)
- Sources: energy = **entsoe_cold_store**, compute = **marketplace** (GLOBAL compute)
- Regional PUE (assumption): FR=1.2, DE=1.45

## Basis amplitude & persistence

| basis | mean (€/GPU·h) | std dev | p95 amplitude | % time dislocated | episodes | half-life (h) |
|---|---|---|---|---|---|---|
| FR−DE | 0.02998 | 0.03569 | 0.08682 | 10.2% | 19 | 4.84 |

## PUE sensitivity

At equal FX and compute price, the basis is driven by `power_kw·(pue_r·energy_r − pue_ref·energy_ref)/1000`: ↑ a region's PUE ⇒ ↑ its cost ⇒ ↓ its spread ⇒ ↓ its basis. Sensitivity is tested (`test_pue_sensitivity_is_monotone`).

## Execution limitations (PoC)

- **Regional PUE** = a strong, poorly observable assumption; the main driver of the basis here.
- **Global compute** (a single curve): revenue cancels out between regions → the basis is essentially an *energy × PUE basis*, not a true regional compute spread.
- **Transfer costs/latency ignored**: do not conclude this is an executable arbitrage.
- Institutional next steps: optimized routing, capacity constraints, tradable signal.
