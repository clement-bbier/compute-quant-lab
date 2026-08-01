# P01 — Digital spark spread pricer synthesis

> Demonstration run of the **point-in-time vectorized pricer** (`core.pricing`).
> Reproducible: `prepare_dataset.py` -> `run_pricer.py` (MLflow). Raw figures:
> [`run_summary.json`](run_summary.json).

## 1. Run coverage

| Item | Value |
|---|---|
| Window | 2025-01-01 -> 2025-01-31 (744 h, UTC) |
| Region / GPU | FR / H100 (8x, TDP 700 W, PUE 1.82) |
| Energy leg | **deterministic synthetic fallback** (no ENTSO-E token in session; real swap = 1 function) |
| Compute leg | Silicon Data stub (H100, mean-reverting, ~2.3 $/GPU·h) |
| FX | 0.92 EUR/$ (constant) |
| Kernel | `PythonOracle` (Rust parity verified bit-for-bit in tests) |

**Honesty note**: the demo run operates on the *synthetic* energy leg
(no ENTSO-E token in the session environment). The real path is coded and
tested (`fetch_energy_entsoe`); it will activate as soon as the token is provided, with no other
change. The figures below therefore illustrate the **mechanics**, not a
market edge measured on real data.

## 2. Results

| Metric (EUR/GPU·h) | Value |
|---|---|
| Mean spread | **2.024** |
| Std dev | 0.110 |
| Min / Max | 1.785 / 2.322 |
| % positive hours | **100 %** |
| Mean revenue (compute) | 2.137 |
| Mean cost (energy) | 0.113 |

## 3. Economic reading

The marginal energy cost of a GPU-hour (**EUR 0.11**) represents only
**~5.3%** of the compute rental price (**EUR 2.14**). The digital spark spread
is therefore **structurally wide and positive** under the current price regime: renting
H100s comfortably covers the electricity consumed (PUE included).

Consequence for the desk: the energy<->compute arbitrage **does not play out** on
the level of the electricity bill under a normal regime — it would take a shock. The
interesting signal will emerge from (a) an **energy shock** (2022-style crisis) or (b) a
**collapse in compute prices** (GPU oversupply). The pricer is the instrument
that will date these shifts in point-in-time.

## 4. PUE / power / energy sensitivity

Implied mean electricity price for the run ≈ **EUR 88.7/MWh**. At constant compute revenue:

| Scenario | Cost EUR/GPU·h | Spread EUR/GPU·h |
|---|---|---|
| Base (PUE 1.82, 0.7 kW) | 0.113 | 2.024 |
| Degraded PUE 2.5 | 0.155 | 1.982 |
| GPU 1.0 kW (Blackwell class) | 0.161 | 1.975 |
| Energy x5 (~443 EUR/MWh, crisis) | 0.565 | 1.572 |
| **Breakeven energy price** | = revenue | **≈ EUR 1,677/MWh** |

The spread is **dominated by the compute price**: PUE and power shift it by
only a few cents. Electricity at ~**EUR 1,677/MWh** (≈ 19x the
average) would be needed to wipe out the margin — hence the asymmetry above.

## 5. Anomalies & edge cases observed (tests)

- **Anti look-ahead**: adding rows with index > t leaves the spread at t
  bit-identical; on a coarser compute grid, backward as-of alignment
  returns the last known price (never the future), and **NaN** before the first
  compute publication (strict point-in-time, no fill from the future).
- **Units/timezone**: EUR/MWh -> EUR/GPU·h conversion validated by hand; point-in-time
  FX; **naive datetime rejected** (UTC tz-aware mandatory); non-UTC tz
  normalized to UTC.
- **Rust<->Python parity**: `np.allclose` on 10,000 random points (bit-exact).
- **DI**: the pricer runs on *mocked* sources/FX/kernel (decoupling proven).

## 6. Reproduce

```bash
# Data (real if ENTSOE_API_TOKEN is in .env, otherwise synthetic fallback)
.venv/Scripts/python.exe projects/01_digital_spark_spread/src/prepare_dataset.py
# Pricing + MLflow run + run_summary.json
.venv/Scripts/python.exe projects/01_digital_spark_spread/src/run_pricer.py
mlflow ui --backend-store-uri experiments/mlruns   # params + metrics + git SHA
```
