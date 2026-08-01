---
paths:
  - "core/ingestion/**"
  - "core/data_quality/**"
  - "data/**"
---
# Data integrity

- `data/raw/` is IMMUTABLE. Never write to it by hand or via a post-ingestion script.
  Every transformation produces a new artifact in `data/interim/`.
- All timestamps are in UTC, timezone-aware. No naive datetime.
- Every ingested series must be committed as plain git-tracked data before a project uses it.
- Document for each source: unit, timezone, frequency, gap-filling method.
- No retroactively revised data may overwrite a historical value
  (preserve point-in-time).
