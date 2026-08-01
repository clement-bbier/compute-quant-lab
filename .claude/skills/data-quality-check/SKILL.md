---
name: data-quality-check
description: Quality validation pipeline for a time series (energy or GPU price) before use. To be invoked after any ingestion and before any backtest.
---
# Data Quality Check

On the target series in `data/interim/`:

1. **Schema**: expected columns, types, sorted and unique UTC time index.
2. **Gaps**: detect gaps vs. the expected frequency; document the fill
   method (bounded forward-fill, interpolation, or drop) — never a silent fill.
3. **Outliers**: flag values outside the physical range (negative electricity prices = possible;
   negative GPU prices = impossible). Log, do not blindly drop.
4. **Point-in-time**: verify that no retroactive revision has overwritten history.
5. **Report**: produce a short summary (n rows, % gaps, n outliers) and only write the
   validated series to `data/processed/` if the checks pass.
