---
paths:
  - "core/models/**"
  - "core/features/**"
  - "projects/**"
---
# Training = versioned cold store (never the hot store)

- Training and backtesting **always** read from the **immutable and
  versioned** cold store (Parquet, plain git-tracked, cf. `docs/storage-roadmap.md`), never a mutable store
  (TimescaleDB / Redis).
- The hot store (real-time serving) is reserved for **live inference** / monitoring,
  not for training reproducibility.
- Every run logs the **git commit** of the data (via `core.utils.tracking`) → a model
  can be retrained identically. An unversioned dataset does not serve as a training base.
