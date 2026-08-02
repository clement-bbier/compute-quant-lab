"""Canonical schema of the compute cold store and frame normalization.

A single place defines the columns of the price lake and guarantees their types
(UTC tz-aware timestamp, float price, integer availability). Writers (collector,
migration) and readers (Parquet, DuckDB) refer to it: the schema is not hardcoded
in the logic (Python quality rule).

Integrity guarantee: a naive timestamp is **rejected** (data-integrity rule — no
ambiguous point-in-time), never silently localized.

Backward compatibility: the optional descriptive columns (``region``,
``gpu_memory_gb``, ``vcpu``, ``ram_gb``, ``disk_gb``, ``provider_detail``) are
tolerated-absent. A Parquet file lacking them can be reloaded without error:
``normalize_frame`` backfills them with ``None``/``NaN``.

Provenance (``simulated``, rule ``forward-real-simulated``): mandatory on
:class:`~core.ingestion.protocols.Snapshot`, but tolerated-absent here for the **same**
backward-compatibility reason as the optional descriptive columns -- every legacy row
written without this column is a real observation (the collector's only mode; there is
no synthetic compute-price fallback), so a legacy row
missing ``simulated`` is backfilled to ``False``, not rejected. This is a documented
provenance fact about the CI collector's history, not a guess.

``ingested_at`` (forward-only): stamps when a row entered the lake (distinct from
``snapshotted_at``, when the price was observed). Mandatory on new writes, tolerated-
absent on legacy rows (backfilled to ``pandas.NaT`` -- "unknown ingestion time", not a
fabricated one). No bi-temporal query support is implemented (see ADR 007): this is a
forward-only audit column, not a point-in-time filter axis.
"""

from __future__ import annotations

import pandas as pd

#: Instant of the reading (UTC tz-aware).
SNAPSHOTTED_AT = "snapshotted_at"
#: Originating marketplace (``vastai``, ``runpod``, ...) — partition column.
SOURCE = "source"
#: Canonical GPU family (``H100``, ...).
GPU_MODEL = "gpu_model"
#: Lease type (``on_demand`` / ``spot`` / ``reserved``) — never aggregated together.
LEASE_TYPE = "lease_type"
#: Price in USD per GPU·hour.
PRICE = "price_usd_per_hour"
#: Number of GPUs offered (proxy for the depth of the reading).
AVAILABILITY = "availability"

# -- Optional descriptive columns ----------------------------------------------
#: Hosting region / datacenter (e.g. ``"EU-FIN-01"``, ``"us-east"``).
REGION = "region"
#: GPU memory in GB (e.g. ``80.0`` for an H100 SXM).
GPU_MEMORY_GB = "gpu_memory_gb"
#: Number of vCPUs of the instance.
VCPU = "vcpu"
#: RAM of the instance in GB.
RAM_GB = "ram_gb"
#: Storage of the instance in GB.
DISK_GB = "disk_gb"
#: Actual sub-provider (useful for aggregators, e.g. Prime Intellect).
PROVIDER_DETAIL = "provider_detail"
#: Real (``False``) vs simulated (``True``) provenance — mandatory on ``Snapshot``,
#: tolerated-absent on legacy rows (backfilled to ``False``; see module docstring).
SIMULATED = "simulated"
#: Instant the row entered the lake (UTC tz-aware) — forward-only, absent on legacy rows.
INGESTED_AT = "ingested_at"

#: Mandatory business columns — all must be present in the frame.
COLUMNS: list[str] = [SNAPSHOTTED_AT, SOURCE, GPU_MODEL, LEASE_TYPE, PRICE, AVAILABILITY]

#: Optional descriptive columns — backfilled when absent (backward compatibility).
OPTIONAL_COLUMNS: list[str] = [REGION, GPU_MEMORY_GB, VCPU, RAM_GB, DISK_GB, PROVIDER_DETAIL]

#: Provenance columns — tolerated-absent (backfilled: ``SIMULATED`` to ``False``,
#: ``INGESTED_AT`` to ``NaT``). Kept distinct from ``OPTIONAL_COLUMNS`` (hardware
#: metadata) because these carry a documented backfill semantic, not just "unknown".
PROVENANCE_COLUMNS: list[str] = [SIMULATED, INGESTED_AT]

#: Complete set of columns of the enriched schema (mandatory + optional + provenance).
ALL_COLUMNS: list[str] = COLUMNS + OPTIONAL_COLUMNS + PROVENANCE_COLUMNS


def normalize_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Project ``frame`` onto the canonical schema and enforce its dtypes.

    The mandatory columns (:data:`COLUMNS`) must be present; the optional columns
    (:data:`OPTIONAL_COLUMNS`) are backfilled with ``None``/``NaN`` when absent —
    which makes the function **backward compatible** with Parquet files that carry
    only the mandatory columns. The provenance columns (:data:`PROVENANCE_COLUMNS`)
    follow the same tolerated-absent contract, with a documented backfill value each
    (see module docstring): ``simulated`` -> ``False``, ``ingested_at`` -> ``NaT``.

    Parameters
    ----------
    frame
        Frame containing at least :data:`COLUMNS` (supernumerary columns are ignored,
        e.g. the ``month`` partition read back from Parquet).

    Returns
    -------
    pandas.DataFrame
        Typed copy: ``snapshotted_at``/``ingested_at`` as ``datetime64[ns, UTC]``,
        ``price`` as ``float64``, ``availability`` as ``int64``, ``simulated`` as
        ``bool``, identifiers as ``str``. Absent optional columns are added with
        ``object`` dtype (value ``None``).

    Raises
    ------
    ValueError
        If a mandatory column is missing, or if ``snapshotted_at``/``ingested_at``
        contains naive instants (without a timezone) — forbidden (point-in-time
        integrity).
    """
    missing = [c for c in COLUMNS if c not in frame.columns]
    if missing:
        raise ValueError(f"frame columns ({missing}) must be present for the cold store schema.")

    # Select the mandatory columns present + the optional/provenance ones present.
    present_optional = [c for c in OPTIONAL_COLUMNS if c in frame.columns]
    present_provenance = [c for c in PROVENANCE_COLUMNS if c in frame.columns]
    out = frame.loc[:, COLUMNS + present_optional + present_provenance].copy()

    # Backfill the absent optional columns (legacy Parquet backward compatibility).
    for col in OPTIONAL_COLUMNS:
        if col not in out.columns:
            out[col] = None

    # Backfill absent provenance columns (legacy rows predate these columns): a row
    # written before `simulated` existed is a real collector observation (the collector's
    # only mode -- no synthetic compute-price fallback exists), never a guessed default.
    if SIMULATED not in out.columns:
        out[SIMULATED] = False
    if INGESTED_AT not in out.columns:
        out[INGESTED_AT] = pd.NaT

    ts = pd.to_datetime(out[SNAPSHOTTED_AT])
    if getattr(ts.dtype, "tz", None) is None:
        if len(ts) > 0:
            raise ValueError("snapshotted_at must be a tz-aware datetime (UTC), not naive.")
        ts = ts.dt.tz_localize("UTC")
    else:
        ts = ts.dt.tz_convert("UTC")

    ingested = pd.to_datetime(out[INGESTED_AT])
    if getattr(ingested.dtype, "tz", None) is None:
        if ingested.notna().any():
            raise ValueError("ingested_at must be a tz-aware datetime (UTC), not naive.")
        ingested = ingested.dt.tz_localize("UTC")
    else:
        ingested = ingested.dt.tz_convert("UTC")

    out[SNAPSHOTTED_AT] = ts
    out[INGESTED_AT] = ingested
    out[SOURCE] = out[SOURCE].astype(str)
    out[GPU_MODEL] = out[GPU_MODEL].astype(str)
    out[LEASE_TYPE] = out[LEASE_TYPE].astype(str)
    out[PRICE] = out[PRICE].astype("float64")
    out[AVAILABILITY] = out[AVAILABILITY].astype("int64")
    out[SIMULATED] = out[SIMULATED].astype("bool")

    # Reorder according to ALL_COLUMNS for a stable schema.
    return out[ALL_COLUMNS].reset_index(drop=True)
