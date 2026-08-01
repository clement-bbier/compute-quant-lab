# P03 — Vol & term structure synthesis

> Demonstration run. Reproducible: `src/run_analysis.py` (MLflow). Raw figures:
> [`run_summary.json`](run_summary.json). MLflow run `bfbeeba40674413a8a77d487c487ccf1`.

## 1. Run coverage

| Item | Value |
|---|---|
| GPU / fix | H100 |
| Spot leg | **demo synthetic** spot (fixed seed), 1.7765 $/GPU·h |
| Forward leg | **SIMULATED** (1-factor Schwartz, `schwartz_mc_python` model) |

**Honesty note**: the compute history is short (recent snapshots). While the
real series remains thin, the run uses a demo-labeled synthetic spot; it switches
to the real index once `data/snapshots/` is deep enough, with no other change.

## 2. Volatility (annualized)

| Estimator | Vol |
|---|---|
| Realized (window 20) | **99.6 %** |
| EWMA (λ=0.94) | **97.4 %** |

## 3. Term structure (SIMULATED) & signal

| Descriptor | Value |
|---|---|
| Shape | **contango** |
| Slope ($/GPU·h/day) | 0.0002221 |
| Curvature (butterfly) | -0.1143 |
| Directional signal | **-1** (contango: negative carry (roll-yield)) |

> Warning: **Real/simulated boundary**: the term structure and signal derive from a
> **simulated** forward curve (`simulated=True`). Conditional on the model, never
> served as an observed market price.

## 4. Limitations

- Short compute history → vol and calibration not very robust (wide interval).
- Simulated forward → the curve's shape reflects the model (Schwartz mean-reversion),
  not an observed market anticipation.
- Roll-yield signal = convention (backwardation→long): to be validated on real data
  once compute futures are listed / the spot series has accumulated.
