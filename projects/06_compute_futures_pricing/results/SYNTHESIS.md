# P06 Synthesis — Theoretical base of compute futures

> WARNING: **THEORETICAL/SIMULATED.** Compute futures (SDH100RT settlement) are
> **not listed**. Forwards come from a model (cost-of-carry / Schwartz P04), never
> from an observed market. Numeric data: [`futures_pricing_summary.json`](futures_pricing_summary.json).

## Demo run assumptions
- Spot: `$2.50/GPU·h` — **source `assumed_fallback`** (no real snapshot accumulated;
  logged fallback). Wire in the real spot index (P04) as soon as the series is available.
- Financing rate `r = 4%/yr`; exogenous convenience yield `y = 1%/yr` (assumption).
- P04 Schwartz forward: `κ=0.05/day, θ=2.5, σ=0.3` (assumed parameters).

## Term structure of the base `F − S` ($/GPU·h)

| Maturity | Carry base (exog. r,y) | P04 forward base | P04 implied yield (annualized) |
|---:|---:|---:|---:|
| 30 d  | +0.0062 | +1.334 | −5.17 |
| 90 d  | +0.0185 | +1.421 | −1.79 |
| 180 d | +0.0372 | +1.421 | −0.87 |
| 360 d | +0.0750 | +1.421 | −0.42 |

- **Exogenous carry**: slight, growing report (`r > y` ⇒ moderate contango).
- **P04 forward**: much higher base — the Schwartz mean reversion (θ + variance
  premium) pushes the forward above the spot; translated into carry terms, this
  yields a **strongly negative implied convenience yield** (holding the position
  "costs" more than financing alone). The two models reconcile exactly via this
  implied yield (consistency tested).

## Sensitivities (carry, at 360 d)
`∂F/∂r = F·τ`, `∂F/∂y = −F·τ`, `∂F/∂τ = F·(r−y)` — analytic, tested. E.g. `∂F/∂τ ≈ 0.077`.

## Desk read
The day of listing, the observed base compares against this theoretical base: a gap
reveals the convenience yield actually priced by the market. Until the futures are
listed, **these figures are a valuation framework, not a tradable signal**.
