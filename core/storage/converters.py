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
    AVAILABILITY,
    COLUMNS,
    GPU_MODEL,
    LEASE_TYPE,
    PRICE,
    SNAPSHOTTED_AT,
    SOURCE,
    normalize_frame,
)


def snapshots_to_frame(snapshots: Sequence[Snapshot]) -> pd.DataFrame:
    """Transforme des :class:`Snapshot` en frame canonique typé (UTC, prix float, dispo int).

    Parameters
    ----------
    snapshots
        Relevés immuables issus de l'ingestion (Vast.ai / RunPod). ``snapshotted_at``
        est déjà UTC tz-aware (garanti par ``Snapshot``).

    Returns
    -------
    pandas.DataFrame
        Frame aux colonnes :data:`COLUMNS`, prêt pour ``PriceStore.write`` (vide si
        ``snapshots`` est vide).
    """
    records = [
        {
            SNAPSHOTTED_AT: pd.Timestamp(s.snapshotted_at),
            SOURCE: s.source,
            GPU_MODEL: s.gpu_model,
            LEASE_TYPE: s.lease_type,
            PRICE: float(s.price_usd_per_hour),
            AVAILABILITY: int(s.availability),
        }
        for s in snapshots
    ]
    return normalize_frame(pd.DataFrame(records, columns=COLUMNS))


def frame_to_snapshots(frame: pd.DataFrame) -> list[Snapshot]:
    """Reconstruit des :class:`Snapshot` depuis un frame canonique (lecture du lac).

    Réciproque de :func:`snapshots_to_frame` : permet à la jambe ingestion (P04) de
    consommer le cold store Parquet via le protocole ``SnapshotStore`` (cf.
    :class:`core.storage.snapshot_store.ParquetSnapshotStore`).
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
        )
        for _, row in frame.iterrows()
    ]
