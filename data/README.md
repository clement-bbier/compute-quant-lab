# Data — layered convention

- `snapshots/` raw data collected hour by hour (multi-venue GPU prices).
  **Versioned in git** as plain files (both CSV and Parquet). This is the
  only irreplaceable layer — compute price has no purchasable history, it
  can only be obtained by accumulating it.
- `raw/`       raw data from an external source, immutable. **Never write here by hand.**
- `interim/`   cleaned / time-aligned.
- `processed/` model-ready (features), produced by the quality checks.
- `cold/`      derived cold store (partitioned Parquet), regenerable.

The derived layers (`raw/`, `interim/`, `processed/`, `cold/`) are not
versioned: they are rebuilt from `snapshots/` and the connectors.

Getting the data after a clone: a plain `git clone` is enough.
