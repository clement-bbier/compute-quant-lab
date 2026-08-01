---
paths:
  - "core/ingestion/**"
  - "core/pricing/**"
  - "projects/**"
---
# Real / simulated boundary (never mix them up)

- Any forward / future curve built by a model is SIMULATED and MUST carry
  an explicit **non-optional** flag (e.g. `Curve.simulated: bool`).
- CME compute futures have been announced but are NOT yet listed (regulatory review):
  every compute forward curve is therefore simulated, never served as real.
- Distinguish REAL (ENTSO-E/PJM, Silicon Data spot) from SIMULATED in both the code AND
  the logs. A test MUST fail if the real/simulated flag is missing.
- The energy leg and the compute spot are real; never mix them with a
  simulated series without explicit labeling.
