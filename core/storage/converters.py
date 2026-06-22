"""Conversion ``Snapshot`` (jambe ingestion P04) → frame canonique du cold store.

Isole l'unique point de couplage *lecture* entre ``core.storage`` et ``core.ingestion`` :
le store ne dépend pas du backend d'ingestion, il consomme ses :class:`Snapshot` immuables
et les projette sur :data:`~core.storage.schema.COLUMNS`. Utilisé par la migration CSV→
Parquet et par le collecteur (écriture du lac).
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
    SNAPSHOTTED_AT,
    SOURCE,
    VCPU,
    normalize_frame,
)


def snapshots_to_frame(snapshots: Sequence[Snapshot]) -> pd.DataFrame:
    """Transforme des :class:`Snapshot` en frame canonique typé (UTC, prix float, dispo int).

    Parameters
    ----------
    snapshots
        Relevés immuables issus de l'ingestion (Vast.ai / RunPod). ``snapshotted_at``
        est déjà UTC tz-aware (garanti par ``Snapshot``). Les champs descriptifs
        optionnels sont propagés quand ils sont renseignés (sinon ``None``).

    Returns
    -------
    pandas.DataFrame
        Frame aux colonnes :data:`ALL_COLUMNS`, prêt pour ``PriceStore.write`` (vide
        si ``snapshots`` est vide).
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
        }
        for s in snapshots
    ]
    return normalize_frame(pd.DataFrame(records, columns=ALL_COLUMNS))


def frame_to_snapshots(frame: pd.DataFrame) -> list[Snapshot]:
    """Reconstruit des :class:`Snapshot` depuis un frame canonique (lecture du lac).

    Réciproque de :func:`snapshots_to_frame` : permet à la jambe ingestion (P04) de
    consommer le cold store Parquet via le protocole ``SnapshotStore`` (cf.
    :class:`core.storage.snapshot_store.ParquetSnapshotStore`). Les colonnes
    optionnelles absentes (Parquet legacy) sont backfillées par ``normalize_frame``.
    """
    frame = normalize_frame(frame)

    def _opt_str(val: object) -> str | None:
        if val is None or (isinstance(val, float) and __import__("math").isnan(val)):
            return None
        return str(val)

    def _opt_float(val: object) -> float | None:
        if val is None:
            return None
        try:
            f = float(val)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None
        import math

        return None if math.isnan(f) else f

    def _opt_int(val: object) -> int | None:
        f = _opt_float(val)
        return None if f is None else int(f)

    return [
        Snapshot(
            snapshotted_at=row[SNAPSHOTTED_AT].to_pydatetime(),
            source=str(row[SOURCE]),
            gpu_model=str(row[GPU_MODEL]),
            price_usd_per_hour=float(row[PRICE]),
            lease_type=str(row[LEASE_TYPE]),
            availability=int(row[AVAILABILITY]),
            region=_opt_str(row.get(REGION)),
            gpu_memory_gb=_opt_float(row.get(GPU_MEMORY_GB)),
            vcpu=_opt_int(row.get(VCPU)),
            ram_gb=_opt_float(row.get(RAM_GB)),
            disk_gb=_opt_float(row.get(DISK_GB)),
            provider_detail=_opt_str(row.get(PROVIDER_DETAIL)),
        )
        for _, row in frame.iterrows()
    ]
