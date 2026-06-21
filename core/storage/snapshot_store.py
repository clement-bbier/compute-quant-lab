"""Adaptateur ``SnapshotStore`` (jambe ingestion P04) sur le cold store Parquet.

Permet à ``build_spot_index`` / ``MarketplaceProxySource`` de lire l'indice depuis le
**cold store versionné** (Parquet + DVC) plutôt que le CSV — conforme à la rule
``training-cold-store``. Pont unique : implémente le protocole
:class:`core.ingestion.protocols.SnapshotStore` en déléguant au
:class:`~core.storage.parquet_store.ParquetPriceStore` via les convertisseurs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from core.ingestion.protocols import Snapshot
from core.storage.converters import frame_to_snapshots, snapshots_to_frame
from core.storage.parquet_store import ParquetPriceStore


class ParquetSnapshotStore:
    """:class:`~core.ingestion.protocols.SnapshotStore` adossé au lac Parquet (P11).

    Append-only et idempotent (hérité de :class:`ParquetPriceStore` : la distribution
    intra-venue est préservée, l'agrégation reste la responsabilité de l'indice P04).
    """

    def __init__(self, root: Path | str) -> None:
        self._store = ParquetPriceStore(root)

    @property
    def root(self) -> Path:
        return self._store.root

    def append(self, rows: Iterable[Snapshot]) -> Path:
        """Append des snapshots au lac (dédup par contenu de ligne) ; renvoie la racine."""
        self._store.write(snapshots_to_frame(list(rows)))
        return self._store.root

    def load(self) -> list[Snapshot]:
        """Recharge tous les snapshots du lac (ordre non garanti)."""
        return frame_to_snapshots(self._store.read())
