# P05 — Risk Review (adversarial)

> The lab's "risk-validator" role: hunt for look-ahead, overfitting, data-snooping and
> the illusion of a "free" arbitrage **before** believing it. Clear-cut verdict per item.

## 1. Look-ahead
The basis itself is point-in-time (backward as-of join in the pricer, inner join between
regions — no future value leaks, proven by `test_no_lookahead_...`). **However**,
`detect_dislocations` computes the `z·std` threshold over **the whole window** (in-sample):
acceptable for a *descriptive metric*, but for a *tradable signal* this is look-ahead (at
time t, the future standard deviation is not known). **Verdict: fine for descriptive PoC,
a real problem as soon as it's traded.** → an expanding/rolling threshold is mandatory.

## 2. "Free" arbitrage
Compute revenue is **global** (same price, same FX): it cancels out, so
`basis = power_kw·(pue_DE·energy_DE − pue_FR·energy_FR)/1000`. This is **not** an
inter-region compute spread: it's a **PUE-weighted electricity price spread** in disguise.
Transfer costs/latency/capacity ignored. **Verdict: false arbitrage at PoC stage** —
"place the load where the spread is widest" is not executable until the transfer is net
of costs.

## 3. PUE assumption
Regional PUE is hardcoded (FR=1.20, DE=1.45), not observable. The basis's **sign and
amplitude** depend directly on it (see `test_pue_sensitivity_is_monotone`). Picking PUE
values that "make" the arbitrage work would be data-snooping. **Verdict: real risk.** →
sourced PUE + uncertainty bands + basis reported as a range, never as a point estimate.

## 4. AR(1) persistence
On **synthetic** data (hourly seasonality + i.i.d. noise), the AR(1) half-life mostly
measures the generator's autocorrelation, not a market property. The observed half-life
of **0.23 h (~14 min)** is shorter than any realistic transfer/execution latency.
**Verdict: not exploitable**; a descriptive figure of the generator, to be recomputed on
the real index.

## 5. Overfitting / data-snooping
Descriptive approach (no train/test split — acceptable since it's non-predictive). But the
**108 "episodes"** are inflated by noise re-crossing the threshold (no minimum duration or
hysteresis) → the count is very noise-sensitive. Promoting this to a signal would require:
multiple windows, tracked `n_trials`, deflated Sharpe. **Verdict: episode count not robust
as-is.**

## Priority guardrails before any tradable signal
1. **Out-of-sample threshold & episodes**: expanding/rolling `std` + minimum duration /
   hysteresis on episodes (otherwise look-ahead + noisy counting).
2. **Sourced PUE with uncertainty**: replace point values with ranges, report the basis's
   sensitivity to PUE bands; never treat a point PUE estimate as ground truth.
3. **Net of transfer costs/latency/capacity** + **real** data (ENTSO-E + real compute
   index) before calling this an executable arbitrage; track `n_trials` (deflated Sharpe).
