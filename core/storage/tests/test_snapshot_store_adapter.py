"""L'indice P04 lit depuis le cold store Parquet via l'adaptateur ``SnapshotStore``."""

from __future__ import annotations

import datetime as dt

import pytest

from core.ingestion.compute_index import MarketplaceProxySource, build_spot_index
from core.ingestion.protocols import Snapshot
from core.storage import ParquetSnapshotStore

_TS = dt.datetime(2026, 6, 21, 12, tzinfo=dt.timezone.utc)


def _seed(store: ParquetSnapshotStore) -> None:
    store.append(
        [
            Snapshot(_TS, "vastai", "H100", 2.0, "on_demand", 1),
            Snapshot(_TS, "vastai", "H100", 2.2, "on_demand", 1),
            Snapshot(_TS, "runpod", "H100", 2.4, "on_demand", 1),
        ]
    )


def test_append_load_preserves_distribution_and_idempotent(tmp_path) -> None:
    store = ParquetSnapshotStore(tmp_path / "lake")
    _seed(store)
    store.append([Snapshot(_TS, "vastai", "H100", 2.0, "on_demand", 1)])  # ré-append = no-op
    snaps = store.load()
    assert len(snaps) == 3  # les 3 offres distinctes conservées (distribution préservée)
    assert {s.source for s in snaps} == {"vastai", "runpod"}


def test_index_reads_from_parquet_cold_store(tmp_path) -> None:
    store = ParquetSnapshotStore(tmp_path / "lake")
    _seed(store)
    src = MarketplaceProxySource(store=store)
    fetched = src.fetch(_TS - dt.timedelta(hours=1), _TS + dt.timedelta(hours=1))
    pt = build_spot_index(fetched, _TS, "H100")
    # vastai -> median(2.0, 2.2) = 2.1 ; runpod -> 2.4 ; trimmed(k=0) = 2.25
    assert pt.n_sources == 2
    assert pt.price_usd_per_hour == pytest.approx(2.25)
