"""TDD tests: optional descriptive fields on ``Snapshot`` and enriched parsers.

Covers:
- (a) ``Snapshot`` accepts the new fields and ``dedup_key`` is unchanged.
- (b) The parsers of the 5 venues do populate the fields when the payload exposes them; they
  leave ``None`` when absent.
- (c) Backward compatibility: a ``Snapshot`` built without the new fields (pre-enrichment
  syntax) keeps working.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest

from core.ingestion.protocols import Snapshot
from core.ingestion.providers import cudo, datacrunch, primeintellect, runpod, vastai

_TS = dt.datetime(2026, 6, 21, tzinfo=dt.timezone.utc)


# -- (a) Snapshot: new fields + unchanged dedup_key ---------------------------


def test_snapshot_accepts_optional_descriptive_fields() -> None:
    s = Snapshot(
        snapshotted_at=_TS,
        source="vastai",
        gpu_model="H100",
        price_usd_per_hour=2.50,
        lease_type="on_demand",
        availability=8,
        region="US, GA",
        gpu_memory_gb=80.0,
        vcpu=64,
        ram_gb=256.0,
        disk_gb=2048.0,
        provider_detail="acme-cloud",
    )
    assert s.region == "US, GA"
    assert s.gpu_memory_gb == 80.0
    assert s.vcpu == 64
    assert s.ram_gb == 256.0
    assert s.disk_gb == 2048.0
    assert s.provider_detail == "acme-cloud"


def test_snapshot_optional_fields_default_to_none() -> None:
    s = Snapshot(
        snapshotted_at=_TS,
        source="runpod",
        gpu_model="A100",
        price_usd_per_hour=1.19,
    )
    assert s.region is None
    assert s.gpu_memory_gb is None
    assert s.vcpu is None
    assert s.ram_gb is None
    assert s.disk_gb is None
    assert s.provider_detail is None


def test_snapshot_dedup_key_excludes_descriptive_fields() -> None:
    """The descriptive fields do NOT enter dedup_key (point-in-time idempotence)."""
    base = Snapshot(
        snapshotted_at=_TS,
        source="vastai",
        gpu_model="H100",
        price_usd_per_hour=2.50,
        lease_type="on_demand",
        availability=8,
    )
    enriched = Snapshot(
        snapshotted_at=_TS,
        source="vastai",
        gpu_model="H100",
        price_usd_per_hour=2.50,
        lease_type="on_demand",
        availability=8,
        region="EU",
        gpu_memory_gb=80.0,
        vcpu=32,
        ram_gb=128.0,
        disk_gb=1000.0,
        provider_detail="some-dc",
    )
    assert base.dedup_key == enriched.dedup_key


def test_snapshot_backward_compat_positional_construction() -> None:
    """Pre-enrichment code (without the new kwargs) compiles and returns None on the optionals."""
    s = Snapshot(
        snapshotted_at=_TS,
        source="cudo",
        gpu_model="H100",
        price_usd_per_hour=2.50,
        lease_type="on_demand",
        availability=4,
    )
    assert s.region is None
    assert s.gpu_memory_gb is None


# -- (b) Parsers: descriptive fields populated from the payload ----------------


def test_vastai_populates_region_and_memory_from_payload() -> None:
    offers: list[dict[str, Any]] = [
        {
            "gpu_name": "H100 SXM",
            "dph_total": 16.0,
            "num_gpus": 8,
            "rentable": True,
            "geolocation": "US, CA",
            "gpu_ram": 81920,  # 80 * 1024 Mo
            "cpu_cores_effective": 64,
            "cpu_ram": 262144,  # 256 * 1024 Mo
            "disk_space": 2048.0,
        }
    ]
    snaps = vastai.parse_vastai_offers(offers, _TS)
    assert len(snaps) == 1
    s = snaps[0]
    assert s.region == "US, CA"
    assert s.gpu_memory_gb == pytest.approx(80.0)
    assert s.vcpu == 64
    assert s.ram_gb == pytest.approx(256.0)
    assert s.disk_gb == pytest.approx(2048.0)
    assert s.provider_detail is None  # vastai is not an aggregator


def test_vastai_none_when_payload_lacks_descriptive_fields(
    vastai_offers: list[dict[str, Any]],
) -> None:
    """Minimal payload (W1 fixture) -> descriptive fields None."""
    snaps = vastai.parse_vastai_offers(vastai_offers, _TS)
    for s in snaps:
        assert s.region is None
        assert s.gpu_memory_gb is None
        assert s.vcpu is None
        assert s.ram_gb is None
        assert s.disk_gb is None


def test_runpod_populates_gpu_memory_gb() -> None:
    gpu_types: list[dict[str, Any]] = [
        {"displayName": "H100 PCIe", "securePrice": 3.50, "communityPrice": 3.20, "memoryInGb": 80},
        {"displayName": "A40", "securePrice": 0.45, "communityPrice": 0},  # no memoryInGb
    ]
    snaps = runpod.parse_runpod_gpu_types(gpu_types, _TS)
    by_model = {s.gpu_model: s for s in snaps}
    assert by_model["H100"].gpu_memory_gb == 80.0
    assert by_model["A40"].gpu_memory_gb is None


def test_runpod_none_for_missing_memory(runpod_gpu_types: list[dict[str, Any]]) -> None:
    """W1 fixture (without memoryInGb) -> gpu_memory_gb == None."""
    snaps = runpod.parse_runpod_gpu_types(runpod_gpu_types, _TS)
    assert all(s.gpu_memory_gb is None for s in snaps)


def test_primeintellect_populates_region_memory_and_provider_detail(
    primeintellect_items: list[dict[str, Any]],
) -> None:
    snaps = primeintellect.parse_primeintellect(primeintellect_items, _TS)
    by_source = {s.source: s for s in snaps}

    h100 = by_source["primeintellect:datacrunch"]
    # region must come from dataCenter (FIN-01) when present
    assert h100.region == "FIN-01"
    assert h100.gpu_memory_gb == 80.0
    assert h100.provider_detail == "datacrunch"

    a100 = by_source["primeintellect:runpod"]
    assert a100.region == "US"  # dataCenter missing -> region
    assert a100.provider_detail == "runpod"

    rtx = by_source["primeintellect"]
    assert rtx.provider_detail is None  # no underlying provider


def test_datacrunch_populates_hardware_specs(
    datacrunch_instance_types: list[dict[str, Any]],
) -> None:
    snaps = datacrunch.parse_datacrunch(datacrunch_instance_types, _TS)
    # it-1 emits on_demand+spot with gpu_memory 640/8 = 80 GB per GPU (fixture: 640 GB for 8)
    h100_snaps = [s for s in snaps if s.gpu_model == "H100"]
    assert len(h100_snaps) == 2  # on_demand + spot
    for s in h100_snaps:
        assert s.gpu_memory_gb == pytest.approx(640.0)  # 640 GB of total GPU memory
        assert s.vcpu == 176
        assert s.ram_gb == pytest.approx(1480.0)
        assert s.disk_gb == pytest.approx(2048.0)

    # it-2 (A100): sub-structures absent -> None
    a100_snaps = [s for s in snaps if s.gpu_model == "A100"]
    assert len(a100_snaps) == 1
    assert a100_snaps[0].gpu_memory_gb is None
    assert a100_snaps[0].vcpu is None


def test_cudo_populates_region_and_gpu_memory(
    cudo_machine_types: list[dict[str, Any]],
) -> None:
    snaps = cudo.parse_cudo(cudo_machine_types, _TS)
    by_model = {s.gpu_model: s for s in snaps}

    h100 = by_model["H100"]
    assert h100.region == "no-luster-1"
    assert h100.gpu_memory_gb == pytest.approx(80.0)

    a40 = by_model["A40"]
    assert a40.region == "se-smedjebacken-1"
    assert a40.gpu_memory_gb is None  # gpuMemoryGib absent from the A40 fixture
