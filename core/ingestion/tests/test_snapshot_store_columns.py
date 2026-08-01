"""Round-trip tests for the 12-column CSV snapshot store.

The store used to persist only the 6 core columns, silently dropping the enriched
descriptive fields (``region``, ``gpu_memory_gb``, ``vcpu``, ``ram_gb``, ``disk_gb``,
``provider_detail``) that the W2 venue wave was built to capture. These tests pin the
full round-trip and the backward compatibility of legacy 6-column files.
"""

from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path

from core.ingestion.protocols import Snapshot
from core.ingestion.snapshot_store import CsvSnapshotStore

_TS = dt.datetime(2026, 6, 21, 12, 0, tzinfo=dt.timezone.utc)

_LEGACY_HEADER = [
    "snapshotted_at",
    "source",
    "gpu_model",
    "lease_type",
    "price_usd_per_hour",
    "availability",
]


def _enriched() -> Snapshot:
    """A snapshot with every optional descriptive field populated."""
    return Snapshot(
        snapshotted_at=_TS,
        source="hyperstack",
        gpu_model="H100",
        price_usd_per_hour=1.9,
        lease_type="on_demand",
        availability=8,
        region="CANADA-1",
        gpu_memory_gb=80.0,
        vcpu=192,
        ram_gb=1800.0,
        disk_gb=32000.0,
        provider_detail="n3-H100x8",
    )


def test_round_trip_preserves_all_twelve_columns(tmp_path: Path) -> None:
    """Every field survives an append/load cycle -- no silent data loss."""
    store = CsvSnapshotStore(tmp_path)
    original = _enriched()

    store.append([original])
    (loaded,) = store.load()

    assert loaded == original


def test_written_header_lists_twelve_columns(tmp_path: Path) -> None:
    """A file created by this version carries the full schema on disk."""
    store = CsvSnapshotStore(tmp_path)
    store.append([_enriched()])

    (path,) = sorted(tmp_path.glob("gpu_prices_*.csv"))
    with path.open(newline="") as f:
        header = next(csv.reader(f))

    assert header == [
        "snapshotted_at",
        "source",
        "gpu_model",
        "lease_type",
        "price_usd_per_hour",
        "availability",
        "region",
        "gpu_memory_gb",
        "vcpu",
        "ram_gb",
        "disk_gb",
        "provider_detail",
    ]


def test_unset_optional_fields_round_trip_as_none(tmp_path: Path) -> None:
    """A bare snapshot stays bare: empty CSV cells decode back to ``None``, not ``""``."""
    store = CsvSnapshotStore(tmp_path)
    bare = Snapshot(_TS, "vastai", "H100", 2.34, lease_type="spot", availability=42)

    store.append([bare])
    (loaded,) = store.load()

    assert loaded == bare
    assert loaded.region is None
    assert loaded.gpu_memory_gb is None
    assert loaded.vcpu is None
    assert loaded.ram_gb is None
    assert loaded.disk_gb is None
    assert loaded.provider_detail is None


def test_reads_legacy_six_column_file(tmp_path: Path) -> None:
    """A CSV written by the 6-column version stays readable; extras decode to ``None``."""
    path = tmp_path / "gpu_prices_202606.csv"
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_LEGACY_HEADER)
        writer.writeheader()
        writer.writerow(
            {
                "snapshotted_at": _TS.isoformat(),
                "source": "runpod",
                "gpu_model": "A100",
                "lease_type": "on_demand",
                "price_usd_per_hour": "1.39",
                "availability": "3",
            }
        )

    (loaded,) = CsvSnapshotStore(tmp_path).load()

    assert loaded.source == "runpod"
    assert loaded.price_usd_per_hour == 1.39
    assert loaded.availability == 3
    assert loaded.region is None
    assert loaded.provider_detail is None


def test_append_to_legacy_file_keeps_its_header_layout(tmp_path: Path) -> None:
    """Appending to a legacy file must not misalign its columns.

    The pre-existing 6-column header is respected; the enriched fields are dropped
    for that file rather than shifting every value one cell to the left.
    """
    path = tmp_path / "gpu_prices_202606.csv"
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_LEGACY_HEADER)
        writer.writeheader()
        writer.writerow(
            {
                "snapshotted_at": _TS.isoformat(),
                "source": "runpod",
                "gpu_model": "A100",
                "lease_type": "on_demand",
                "price_usd_per_hour": "1.39",
                "availability": "3",
            }
        )

    store = CsvSnapshotStore(tmp_path)
    store.append([_enriched()])

    loaded = {s.source: s for s in store.load()}
    assert set(loaded) == {"runpod", "hyperstack"}
    # Core columns stay correctly aligned for the row appended to the legacy file.
    assert loaded["hyperstack"].price_usd_per_hour == 1.9
    assert loaded["hyperstack"].availability == 8
    assert loaded["hyperstack"].gpu_model == "H100"


def test_idempotence_is_unaffected_by_the_new_columns(tmp_path: Path) -> None:
    """Descriptive fields are not part of the dedup key, so they never split a row."""
    store = CsvSnapshotStore(tmp_path)
    bare = Snapshot(_TS, "hyperstack", "H100", 1.9, availability=8)

    store.append([_enriched()])
    store.append([bare])  # same natural key, different metadata -> still a duplicate

    assert len(store.load()) == 1
