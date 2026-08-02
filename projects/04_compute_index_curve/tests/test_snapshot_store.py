"""Tests of the idempotent append-only storage for compute price snapshots."""

from __future__ import annotations

import datetime as dt

from core.ingestion.protocols import Snapshot
from core.ingestion.snapshot_store import CsvSnapshotStore

_TS = dt.datetime(2026, 6, 21, 12, 0, tzinfo=dt.timezone.utc)


def test_append_is_idempotent(tmp_path) -> None:
    store = CsvSnapshotStore(tmp_path)
    a = Snapshot(_TS, "vastai", "H100", 2.0, simulated=False)
    b = Snapshot(_TS, "runpod", "H100", 2.2, simulated=False)
    c = Snapshot(_TS, "lambda", "H100", 2.1, simulated=False)

    store.append([a, b])
    store.append([a, c])  # a is a duplicate -> ignored

    assert len(store.load()) == 3

    store.append([a, b, c])  # all duplicates -> no growth
    assert len(store.load()) == 3


def test_round_trip_preserves_values(tmp_path) -> None:
    store = CsvSnapshotStore(tmp_path)
    a = Snapshot(_TS, "vastai", "H100", 2.34, lease_type="spot", availability=42, simulated=False)
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
    on_demand = Snapshot(_TS, "vastai", "H100", 2.0, lease_type="on_demand", simulated=False)
    spot = Snapshot(_TS, "vastai", "H100", 1.5, lease_type="spot", simulated=False)

    store.append([on_demand, spot])
    assert len(store.load()) == 2  # different lease -> not a duplicate
