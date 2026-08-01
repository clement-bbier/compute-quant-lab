"""``SnapshotStore`` adapter (P04 ingestion leg) over the Parquet cold store.

Lets ``build_spot_index`` / ``MarketplaceProxySource`` read the index from the
**versioned cold store** (Parquet, plain git) rather than the CSV — compliant with the
``training-cold-store`` rule. Single bridge: implements the
:class:`core.ingestion.protocols.SnapshotStore` protocol by delegating to
:class:`~core.storage.parquet_store.ParquetPriceStore` through the converters.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from core.ingestion.protocols import Snapshot
from core.storage.converters import frame_to_snapshots, snapshots_to_frame
from core.storage.parquet_store import ParquetPriceStore


class ParquetSnapshotStore:
    """:class:`~core.ingestion.protocols.SnapshotStore` backed by the Parquet lake (P11).

    Append-only and idempotent (inherited from :class:`ParquetPriceStore`: the intra-venue
    distribution is preserved, aggregation remains the responsibility of the P04 index).
    """

    def __init__(self, root: Path | str) -> None:
        self._store = ParquetPriceStore(root)

    @property
    def root(self) -> Path:
        return self._store.root

    def append(self, rows: Iterable[Snapshot]) -> Path:
        """Append snapshots to the lake (dedup by row content); returns the root."""
        self._store.write(snapshots_to_frame(list(rows)))
        return self._store.root

    def load(self) -> list[Snapshot]:
        """Reload every snapshot from the lake (order not guaranteed)."""
        return frame_to_snapshots(self._store.read())
