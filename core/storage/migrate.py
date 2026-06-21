"""Migration du cold store historique : CSV mensuels (P04) → lac Parquet (Phase 0).

Bascule la série propriétaire ``data/snapshots/gpu_prices_*.csv`` vers le lac Parquet
partitionné, **sans perte** : la lecture réutilise le ``CsvSnapshotStore`` de P04 (donc
le format CSV reste sa source de vérité), puis ``PriceStore.write`` (idempotent) absorbe
les lignes. Rejouer la migration est un no-op (aucun doublon).
"""

from __future__ import annotations

from pathlib import Path

from core.ingestion.snapshot_store import CsvSnapshotStore
from core.storage.converters import snapshots_to_frame
from core.storage.protocols import PriceStore


def migrate_csv_snapshots(csv_dir: Path | str, store: PriceStore) -> int:
    """Migre les snapshots CSV de ``csv_dir`` vers ``store`` ; renvoie le nb de lignes neuves.

    Parameters
    ----------
    csv_dir
        Répertoire des ``gpu_prices_YYYYMM.csv`` (lu via ``CsvSnapshotStore``).
    store
        Cold store de destination (typiquement un ``ParquetPriceStore``).

    Returns
    -------
    int
        Nombre de lignes effectivement écrites (0 si déjà migré ou répertoire vide).
    """
    snapshots = CsvSnapshotStore(Path(csv_dir)).load()
    return store.write(snapshots_to_frame(snapshots))
