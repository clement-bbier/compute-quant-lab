# P06 — Compute Futures Pricing (theoretical / simulated)

**Theoretical** pricing of compute futures (CME, settling on the Silicon Data index
SDH100RT, **not listed**): spot/forward base and sensitivities, ready to value the
day it lists. See the local spec: [CLAUDE.md](CLAUDE.md).

> WARNING: **THEORETICAL/SIMULATED.** Compute futures are not listed. Every forward
> comes from a model (cost-of-carry or Schwartz P04), never from an observed market.
> Each `FuturesQuote` carries a mandatory `simulated` field; never present these
> figures as a real price.

## Model

### Cost-of-carry
Forward price of an underlying carrying a financing cost `r` and a convenience
yield `y` (annualized), at maturity `τ` (years):

```
F = S · e^{(r − y)·τ}        base = F − S
```

- **Contango** if `r > y` (positive base), **backwardation** if `y > r`.
- **Convergence**: `F(τ=0) = S`.
- **Sensitivities** (analytic first derivatives): `∂F/∂r = F·τ`,
  `∂F/∂y = −F·τ`, `∂F/∂τ = F·(r−y)`.

### Implicit convenience yield (the pivot)
The yield `y` is **not observable**. It is inferred by inverting the forward:

```
y = r − ln(F/S) / τ
```

`CarryFuturesPricer` **systematically** infers this yield from the injected forward.
Consequence: for an exogenous `CostOfCarryModel(r, y)`, the inversion **returns `y`**
(round-trip); for P04's **simulated Schwartz** forward, it **extracts** the implicit
yield — a single framework for two dynamics (geometric carry vs mean reversion).

## Architecture

| Element | Location | Role |
|---|---|---|
| `CarryModel`, `FuturesPricer` | `core/pricing/derivatives/protocols.py` | Contracts (DI / SOLID) |
| `carry_forward`, `implied_convenience_yield`, `carry_sensitivities`, `CostOfCarryModel` | `core/pricing/derivatives/carry.py` | Core (pure functions) |
| `FuturesQuote`, `CarryFuturesPricer` | `core/pricing/derivatives/futures.py` | Quoting + orchestrator |
| `P04ForwardAdapter` | `src/p04_forward_adapter.py` | Bridge to P04's Schwartz forward |
| `run_pricing.py` | `src/run_pricing.py` | End-to-end demo + MLflow |

The P04 adapter lives in the **project layer** (not in `core/`) so as not to couple
the core to `projects/04`: `core` stays agnostic of projects, `mypy core` stays clean.

## Run

```bash
uv sync --extra dev
# Demo: real spot (logged fallback if no snapshot), term structure, MLflow run
uv run python projects/06_compute_futures_pricing/src/run_pricing.py
# Output: results/futures_pricing_summary.json (+ run under experiments/mlruns)

# Tests (outside testpaths until convergence patches pyproject.toml)
uv run pytest projects/06_compute_futures_pricing/tests
```

## Reproducibility
MLflow run (`p06_compute_futures_pricing`) logging params (spot + real/assumed source,
`r`, `y`, Schwartz params, maturity grid, `simulated=True`), metrics (base and implied
yield per maturity), git SHA and DVC version (via `core.utils.tracking.run`).
Deterministic analytic oracle (no Monte Carlo) → reproducible result.

## Limitations & blind spots
- Futures **not listed** → 100% theoretical.
- **Convenience yield** not observable: assumed (exogenous carry) or inferred (P04 forward).
- Dependency on P04's Schwartz model: **the forward is not the market**.
- Real spot not yet accumulated (snapshots) → the demo falls back to a logged assumption.
