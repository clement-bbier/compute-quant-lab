"""``Snapshot`` (P04 ingestion leg) to cold store canonical frame conversion.

Isolates the single *read* coupling point between ``core.storage`` and ``core.ingestion``:
the store does not depend on the ingestion backend, it consumes its immutable
:class:`Snapshot` objects and projects them onto :data:`~core.storage.schema.COLUMNS`.
Used by the CSV to Parquet migration and by the collector (lake writing).
"""

from __future__ import annotations

from typing import Sequence

import pandas as pd

from core.ingestion.protocols import Snapshot
from core.storage.schema import (
    ALL_COLUMNS,
    AVAILABILITY,
    DISK_GB,
    GPU_MEMORY_GB,
    GPU_MODEL,
    LEASE_TYPE,
    PRICE,
    PROVIDER_DETAIL,
    RAM_GB,
    REGION,
    SIMULATED,
    SNAPSHOTTED_AT,
    SOURCE,
    VCPU,
    normalize_frame,
)
from core.utils.coerce import lenient_float, lenient_int, lenient_str


def snapshots_to_frame(snapshots: Sequence[Snapshot]) -> pd.DataFrame:
    """Turn :class:`Snapshot` objects into a typed canonical frame (UTC, float price, int avail).

    Parameters
    ----------
    snapshots
        Immutable readings coming from ingestion (Vast.ai / RunPod). ``snapshotted_at``
        is already UTC tz-aware (guaranteed by ``Snapshot``). The optional descriptive
        fields are propagated when they are populated (otherwise ``None``). ``simulated``
        is always populated (mandatory on ``Snapshot``); ``ingested_at`` is left absent
        here and backfilled by the store on write (the store, not the snapshot, owns the
        instant of ingestion).

    Returns
    -------
    pandas.DataFrame
        Frame with the :data:`ALL_COLUMNS` columns, ready for ``PriceStore.write`` (empty
        if ``snapshots`` is empty).
    """
    records = [
        {
            SNAPSHOTTED_AT: pd.Timestamp(s.snapshotted_at),
            SOURCE: s.source,
            GPU_MODEL: s.gpu_model,
            LEASE_TYPE: s.lease_type,
            PRICE: float(s.price_usd_per_hour),
            AVAILABILITY: int(s.availability),
            REGION: s.region,
            GPU_MEMORY_GB: s.gpu_memory_gb,
            VCPU: s.vcpu,
            RAM_GB: s.ram_gb,
            DISK_GB: s.disk_gb,
            PROVIDER_DETAIL: s.provider_detail,
            SIMULATED: s.simulated,
        }
        for s in snapshots
    ]
    return normalize_frame(pd.DataFrame(records, columns=ALL_COLUMNS))


def frame_to_snapshots(frame: pd.DataFrame) -> list[Snapshot]:
    """Rebuild :class:`Snapshot` objects from a canonical frame (reading the lake).

    Inverse of :func:`snapshots_to_frame`: lets the ingestion leg (P04) consume the
    Parquet cold store through the ``SnapshotStore`` protocol (see
    :class:`core.storage.snapshot_store.ParquetSnapshotStore`). Absent optional
    columns (legacy Parquet) are backfilled by ``normalize_frame``. ``ingested_at`` is
    a store-only audit column (not a ``Snapshot`` field) and is dropped here, not
    round-tripped.
    """
    frame = normalize_frame(frame)
    return [
        Snapshot(
            snapshotted_at=row[SNAPSHOTTED_AT].to_pydatetime(),
            source=str(row[SOURCE]),
            gpu_model=str(row[GPU_MODEL]),
            price_usd_per_hour=float(row[PRICE]),
            lease_type=str(row[LEASE_TYPE]),
            availability=int(row[AVAILABILITY]),
            region=lenient_str(row.get(REGION)),
            gpu_memory_gb=lenient_float(row.get(GPU_MEMORY_GB)),
            vcpu=lenient_int(row.get(VCPU)),
            ram_gb=lenient_float(row.get(RAM_GB)),
            disk_gb=lenient_float(row.get(DISK_GB)),
            provider_detail=lenient_str(row.get(PROVIDER_DETAIL)),
            simulated=bool(row[SIMULATED]),
        )
        for _, row in frame.iterrows()
    ]
