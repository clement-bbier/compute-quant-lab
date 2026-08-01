# L0 — Preregistration sheet: ERCOT grid stress -> RTM spike

> **Status: SIGNED on 2026-06-23 (pilot / convergence session).**
> Frozen document. Any change to a hypothesis, a predictor, a threshold or a
> metric after this date opens a **new** L0 sheet — never an amendment. This
> is the anti-p-hacking contract that Worktrees A and B reference.

## 0. Object and honest framing

We test whether the **ex ante forecast of ERCOT grid tension** (known the
evening before) predicts **sustained scarcity events** in the real-time
market (RTM) the next day, **beyond** a naive seasonal climatology.

**What this sheet is**: a point-in-time pipeline validation + a measurement
of predictive skill on a **quasi-structural** relationship (the ORDC
mechanism mechanically ties reserves and scarcity prices). The result
de-risks the energy machinery and calibrates the effect.

**What this sheet is NOT**: a claim of new alpha. The targeted alpha —
electricity -> compute price dislocation — is the **deferred cross-leg**,
gated on cold-store accumulation. It is not tested here.

## 1. Hypotheses

- **H1 (tested)**: the grid-tension predictor vector forecast at T improves
  the prediction of RTM scarcity events at T+h **strictly above** the
  climatological baseline.
- **H0 (null)**: no skill gain over the baseline (model PR-AUC <= baseline
  PR-AUC, confidence interval included).

Confirming H1 **and** rejecting H1 are **both successes**: either one
validates the pipeline and informs what comes next.

## 2. Market and provenance

- **Market**: ERCOT (Texas).
- **Source**: **real** ERCOT data via `gridstatus` (public, no token
  needed). Any simulated point would carry a non-optional `simulated=True`
  flag (rule `forward-real-simulated`). Here: **100% real**.
- **To be checked by `data-engineer` at ingestion** (without changing this
  sheet): exact names of the ERCOT reports and their **actual publication
  times**, to guarantee the predictor's point-in-time nature.

## 3. Predictor (FROZEN set)

Vector known at **~18:00 CPT on day J-1** (decision cutoff):

1. **Forecast reserve margin** (MW) = forecast capacity - forecast load, for
   the target hours of day J, taken from the latest ERCOT forecast report
   published **before** the cutoff.
2. **Forecast net-load gradient** (first derivative over the target window):
   captures the *speed* of margin collapse at sunset (duck curve).

> **The set is closed to these 2 predictors.** No addition ("just one more
> feature") without opening a new L0 sheet. Each extra predictor is a degree
> of freedom counted against the spec budget (section 7).

## 4. Target label (predicted event)

- **Primary definition**: **sustained RTM spike** = system-wide **hourly
  integrated** RTM price (time-weighted average over the hour) **> tau**.
  Hourly integration filters out 5/15-min microstructure noise by
  construction (an isolated blip does not trigger it).
- **Duration robustness check**: >= 2 **consecutive** 15-min intervals > tau.
- **Secondary label (zonal)**: same definition on the `HB_WEST` hub
  (datacenter/mining concentration). *Secondary only*: the predictor in
  section 3 is system-wide; a zonal spike can come from local congestion
  that this metric does not capture. Zonalization becomes **primary** once
  the instance-to-hub mapping exists (deferred cross-leg).

## 5. Threshold tau (spike definition)

- **Primary**: hourly RTM price > **99th percentile conditional on
  hour-of-day**, estimated on a **causal trailing window** (only data known
  at t). The hour-of-day conditioning neutralizes the intraday shape
  (otherwise every ordinary daytime peak would be flagged).
- **Robustness check**: absolute threshold > **$1,500/MWh** (genuine
  scarcity, not the $250 of an ordinary Texan summer afternoon).

## 6. Lag and causality

- Predictor known ~18:00 J-1 -> label realized over the hours of day J.
  **Strictly causal**: the label cannot be known before the predictor's timestamp.
- We target the **RTM** (not the DAM) precisely for this reason: day J's DAM
  clears around 13:30 on J-1, *before* the 18:00 cutoff -> using it would be look-ahead.

## 7. Evaluation (anti-p-hacking, frozen ex ante)

- **Baseline to beat**: **hour-of-day x month** climatology (seasonal base
  rate). H1 is only validated if the model **beats** this baseline.
- **Primary metric**: **threshold-free PR-AUC** + full Precision-Recall
  curve + **reliability diagram** (calibration). A *threshold-free* and
  *policy-free* metric by choice: signal quality is measured independently
  of any operating point.
- **NO cost asymmetry here.** The false-negative / false-positive asymmetric
  loss function is a **Desk-layer concern** (P10/P12), to be **derived**
  from real economics (EUR/MWh of exposure x instance savings), never
  guessed. Out of scope for L0.
- **Split**: chronological, **purged + embargo** (P09 machinery). Holdout =
  last chronological **30%**, **frozen** before any look. **7-day** embargo
  around the cutoff.
- **Spec budget**: **N = 4** specifications maximum allowed (the 2 tau
  thresholds x the 2 primary/secondary labels). **Benjamini-Hochberg**
  multiplicity correction across these 4. Any spec beyond that = a new sheet.
- **Outlier policy (frozen)**: **Winter Storm Uri** (Feb. 2021) **included**
  in the sample, **plus** a separate sensitivity analysis **with / without**
  Uri (a 100-sigma event that would dominate any unguarded fit).
- **Decision criterion**: H1 is retained if, on the **holdout**, the model's
  PR-AUC exceeds the upper bound of the bootstrap CI (1000 resamples) of the
  baseline's PR-AUC, on the primary spec, after BH correction.
- **Stopping rule**: once the holdout has been evaluated on the 4 specs,
  **stop**. No post-holdout re-tuning. Any new cycle = a new dated sheet.

## 8. PUE prior — Worktree A (orthogonal to this test)

Documented here for traceability, but **not part of** the test in sections
1-7: the PUE only affects **pricing** (compute-energy spread, Worktree A),
not the stress->price relationship (Worktree B). Reassuring: the first
validation does not depend on the most uncertain parameter.

- **Distribution**: **truncated normal**, mu=1.45, sigma=0.15, **support
  [1.2, 1.8]** (respects PUE >= 1 by construction; Texas centered higher for cooling).
- **Usage**: **strict prior**, never updated from observed prices (fitting
  to price is forbidden). Propagated as **sensitivity bands** in the pricing outputs.
- **Calibration note**: anchor the center on published averages (Uptime
  global ~= 1.55; hyperscale ~= 1.1-1.2; heterogeneous spot hosts -> real
  dispersion possibly wider than sigma=0.15; revisit in a dedicated sheet if needed).

## 9. Inherited guardrails (non-negotiable)

- Strict point-in-time everywhere (as_of, lags, revisions) — `core/features` machinery.
- Real / simulated boundary labeled (rule `forward-real-simulated`).
- Every backtest/calibration logged to MLflow + git SHA.
- Mandatory gates: `data-quality-auditor` (ingestion) -> `backtest-pitfalls`
  + `risk-validator` pass (before trusting a result) -> pilot convergence.
