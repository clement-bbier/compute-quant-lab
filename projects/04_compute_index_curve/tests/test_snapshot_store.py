"""Tests du stockage append-only idempotent des snapshots de prix compute."""

from __future__ import annotations

import datetime as dt

from core.ingestion.protocols import Snapshot
from core.ingestion.snapshot_store import CsvSnapshotStore

_TS = dt.datetime(2026, 6, 21, 12, 0, tzinfo=dt.timezone.utc)


def test_append_is_idempotent(tmp_path) -> None:
    store = CsvSnapshotStore(tmp_path)
    a = Snapshot(_TS, "vastai", "H100", 2.0)
    b = Snapshot(_TS, "runpod", "H100", 2.2)
    c = Snapshot(_TS, "lambda", "H100", 2.1)

    store.append([a, b])
    store.append([a, c])  # a est un doublon -> ignoré

    assert len(store.load()) == 3

    store.append([a, b, c])  # tout en doublon -> aucune croissance
    assert len(store.load()) == 3


def test_round_trip_preserves_values(tmp_path) -> None:
    store = CsvSnapshotStore(tmp_path)
    a = Snapshot(_TS, "vastai", "H100", 2.34, lease_type="spot", availability=42)
    store.append([a])

    (loaded,) = store.load()
    assert loaded.source == "vastai"
    assert loaded.gpu_model == "H100"
    assert loaded.price_usd_per_hour == 2.34
    assert loaded.lease_type == "spot"
    assert loaded.availability == 42
    assert loaded.snapshotted_at == _TS


def test_dedup_key_distinguishes_lease_type(tmp_path) -> None:
    store = CsvSnapshotStore(tmp_path)
    on_demand = Snapshot(_TS, "vastai", "H100", 2.0, lease_type="on_demand")
    spot = Snapshot(_TS, "vastai", "H100", 1.5, lease_type="spot")

    store.append([on_demand, spot])
    assert len(store.load()) == 2  # bail différent -> pas un doublon
