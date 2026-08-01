# 6. `simulated` is a mandatory, no-default field, not a convention

## Status
Accepted — 2026-06

## Context
Compute futures (CME, settling on a Silicon Data-style index) are announced
but not listed pending regulatory review, so every compute forward/futures
curve in the lab is necessarily theoretical. Several projects also fall back
to synthetic data when a real data token isn't configured (P01 energy, P02
compute snapshots, P05 regional basis, P07 exogenous variables). Early on,
whether a given series was real or simulated was tracked by convention
(a docstring, a variable name) — which is exactly the kind of claim that
silently drifts, as later happened when `projects/01_digital_spark_spread/
results/run_summary.json` asserted `"energy_source": "entsoe_real"` while the
same run's `SYNTHESIS.md` said it had fallen back to synthetic data.

## Decision
- Any type carrying a forward/simulated value (`Curve`, `FuturesQuote`,
  `DataProvenance`, `SignalProvenance`, `TermStructure`) declares `simulated:
  bool` as a **required field with no default**. Constructing one without
  specifying it is a type error, not a silently-wrong default.
- A dedicated test per module asserts the field's absence fails
  construction (red-first), enforced by the `forward-real-simulated` rule.
- Real data (ENTSO-E, marketplace snapshots, the ERCOT cold store) is never
  mixed with a simulated series without an explicit, propagated label; the
  label is logged to MLflow alongside the run.

## Consequences
- The real/simulated boundary is enforced by the type system at every call
  site that constructs one of these values, not by hoping every author
  remembers to set a flag correctly.
- It does not, by itself, prevent a downstream artifact (a committed JSON
  summary, a `CLAUDE.md` progress table) from asserting something the flag
  contradicts — that class of drift is a documentation-sync problem, not a
  types problem, and needs a separate check (e.g. regenerating artifacts
  from the pipeline rather than hand-editing them) if it recurs.
