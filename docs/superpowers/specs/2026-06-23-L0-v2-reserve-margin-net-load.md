# L0-v2 — Amendment to the reserve margin predictor (ERCOT)

> **Status: SIGNED on 2026-06-23 (pilot session).** Amends section 3 of
> [L0](2026-06-23-L0-ercot-grid-stress-preregistration.md). **Only the
> reserve margin predictor changes**; everything else in L0 (RTM spike
> label, 18h J-1 lag, threshold-free PR-AUC metric, purged+embargo split,
> 4-spec/BH budget, climatological baseline, Uri policy) is **UNCHANGED**.

## Reason (discovered during implementation on real data)

The v1 reserve margin = `forecast capacity - forecast load (gross)` at `as_of
= 18h J-1`. During the summer 2022 backfill, the hosted `ercot_load_forecast`
dataset turns out to be a **short-term** product (~1h horizon, 5-min
granularity): at the 18h J-1 cutoff it **does not yet cover** day J.
Point-in-time diagnosis confirmed:

| Leg (at the 18h J-1 cutoff) | Covers day J? |
|---|---|
| available capacity (STSA, 7 days) | yes |
| forecast net-load (7 days) | yes |
| **gross load (`ercot_load_forecast`, short-term)** | no |

The **7-day load** forecast is another hosted dataset, **not backfilled**
(free quota exhausted). v1 is therefore not computable as specified.

## Amendment (section 3 — reserve margin predictor)

Forecast reserve margin = **`available capacity (STSA) - forecast
net-load`** at `as_of = 18h J-1` (instead of `capacity - gross load`).

**Methodological justification**: **net-load** (demand minus renewable
generation) is precisely the load that **dispatchable capacity must serve**.
`capacity - net-load` measures **actual grid tension** more faithfully than
`capacity - gross load`, which ignores the renewable contribution on the
supply side. The amendment is therefore both a *data-availability
constraint* **and** a defensible refinement.

The **second predictor** (net-load gradient) and the **label** (RTM spike) are unchanged.

## Guardrails (unchanged from L0)

Strict point-in-time (`publish_time <= as_of`, `_latest_known_per_interval`
guardrail), purged + embargo, threshold-free PR-AUC, Benjamini-Hochberg on
the spec budget, MLflow run + git SHA (the data lives in the same git
history, tracked as plain files, so that SHA already pins the exact dataset
version). **Reverting to v1** (gross load) remains possible if the 7-day
load forecast dataset gets wired up (quota / paid tier).
