"""Tests of the Hyperstack connector: ``flavor.gpu`` to pricebook join (per-GPU price).

Real model (verified live 2026-06-23): the pricebook is **per component**, ``value`` is a
**string** giving the price **already per GPU**; the join is done on ``flavor.gpu`` (GPU type,
e.g. ``"H100-80G-PCIe"``), not on ``flavor.name``. The ``-spot`` suffix of the type sets the
lease. TDD pattern: ``parse_hyperstack`` is called directly (zero network).
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest

from core.ingestion.providers import hyperstack
from core.ingestion.providers.hyperstack import (
    _build_price_index,
    _coerce_price,
    _vram_gb,
    fetch_hyperstack,
    parse_hyperstack,
)

_TS = dt.datetime(2026, 6, 23, tzinfo=dt.timezone.utc)


# -- _coerce_price / _build_price_index ----------------------------------------


def test_coerce_price_parses_string_values() -> None:
    assert _coerce_price("1.9") == 1.9
    assert _coerce_price(2) == 2.0


def test_coerce_price_rejects_zero_and_invalid() -> None:
    assert _coerce_price("0E-9") is None  # zero component (decimal string)
    assert _coerce_price("-1.0") is None
    assert _coerce_price(None) is None
    assert _coerce_price("abc") is None


def test_build_price_index_coerces_strings_and_drops_zero(
    hyperstack_pricebook: list[dict[str, Any]],
) -> None:
    idx = _build_price_index(hyperstack_pricebook)
    assert idx["H100-80G-PCIe"] == 1.9
    assert idx["H100-80G-PCIe-spot"] == 1.52
    assert idx["L40"] == 0.99
    assert "vCPU" not in idx  # value "0E-9" -> discarded


def test_build_price_index_skips_missing_name_or_value() -> None:
    pricebook: list[dict[str, Any]] = [
        {"name": "X", "value": "5"},
        {"value": "3"},  # no name
        {"name": None, "value": "2"},
        {"name": "Y"},  # no value
    ]
    assert _build_price_index(pricebook) == {"X": 5.0}


# -- _vram_gb ------------------------------------------------------------------


def test_vram_gb_extracts_memory_from_type() -> None:
    assert _vram_gb("H100-80G-PCIe") == 80.0
    assert _vram_gb("H200-141G-SXM5") == 141.0
    assert _vram_gb("B200-SXM") is None
    assert _vram_gb("L40") is None


# -- parse_hyperstack ----------------------------------------------------------


def test_parse_hyperstack_joins_on_gpu_type_per_gpu_price(
    hyperstack_flavors: list[dict[str, Any]],
    hyperstack_pricebook: list[dict[str, Any]],
) -> None:
    snaps = parse_hyperstack(hyperstack_flavors, hyperstack_pricebook, _TS)
    # 2 H100 on_demand + 1 H100 spot + 1 L40; cpu-small and A100 (not in pricebook) discarded
    assert len(snaps) == 4
    assert all(s.source == "hyperstack" for s in snaps)
    # the pricebook price is ALREADY per GPU: no n3-H100* is worth 1.9/8
    h100_od = [s for s in snaps if s.gpu_model == "H100" and s.lease_type == "on_demand"]
    assert len(h100_od) == 2
    assert all(s.price_usd_per_hour == 1.9 for s in h100_od)


def test_parse_hyperstack_spot_suffix_sets_lease_and_clean_model(
    hyperstack_flavors: list[dict[str, Any]],
    hyperstack_pricebook: list[dict[str, Any]],
) -> None:
    snaps = parse_hyperstack(hyperstack_flavors, hyperstack_pricebook, _TS)
    spot = [s for s in snaps if s.lease_type == "spot"]
    assert len(spot) == 1
    assert spot[0].gpu_model == "H100"  # "-spot" stripped before normalisation (not "L40S")
    assert spot[0].price_usd_per_hour == 1.52


def test_parse_hyperstack_populates_descriptive_fields(
    hyperstack_flavors: list[dict[str, Any]],
    hyperstack_pricebook: list[dict[str, Any]],
) -> None:
    snaps = parse_hyperstack(hyperstack_flavors, hyperstack_pricebook, _TS)
    big = next(s for s in snaps if s.vcpu == 192)
    assert big.gpu_model == "H100"
    assert big.region == "CANADA-1"
    assert big.gpu_memory_gb == 80.0
    assert big.ram_gb == 1800.0
    assert big.disk_gb == 32000.0


def test_parse_hyperstack_stock_available_false_gives_zero(
    hyperstack_flavors: list[dict[str, Any]],
    hyperstack_pricebook: list[dict[str, Any]],
) -> None:
    snaps = parse_hyperstack(hyperstack_flavors, hyperstack_pricebook, _TS)
    l40 = next(s for s in snaps if s.gpu_model == "L40")
    assert l40.availability == 0
    assert l40.gpu_memory_gb is None  # "L40" carries no memory in the type


def test_parse_hyperstack_skips_gpu_absent_from_pricebook(
    hyperstack_flavors: list[dict[str, Any]],
    hyperstack_pricebook: list[dict[str, Any]],
) -> None:
    snaps = parse_hyperstack(hyperstack_flavors, hyperstack_pricebook, _TS)
    assert all(s.gpu_model != "A100" for s in snaps)  # A100-80G-SXM4 hors pricebook


def test_parse_hyperstack_skips_zero_gpu_count(
    hyperstack_pricebook: list[dict[str, Any]],
) -> None:
    groups = [
        {
            "gpu": "L40",
            "flavors": [{"name": "cpu", "gpu": "L40", "gpu_count": 0, "stock_available": True}],
        }
    ]
    assert parse_hyperstack(groups, hyperstack_pricebook, _TS) == []


def test_parse_hyperstack_empty_pricebook_returns_empty(
    hyperstack_flavors: list[dict[str, Any]],
) -> None:
    assert parse_hyperstack(hyperstack_flavors, [], _TS) == []


def test_parse_hyperstack_falls_back_to_group_gpu(
    hyperstack_pricebook: list[dict[str, Any]],
) -> None:
    # flavor without 'gpu' -> fall back to the group's 'gpu' for the join
    groups = [
        {"gpu": "L40", "flavors": [{"name": "n3-L40x1", "gpu_count": 1, "stock_available": True}]}
    ]
    snaps = parse_hyperstack(groups, hyperstack_pricebook, _TS)
    assert len(snaps) == 1
    assert snaps[0].gpu_model == "L40"
    assert snaps[0].price_usd_per_hour == 0.99


def test_parse_hyperstack_snapshotted_at_preserved(
    hyperstack_flavors: list[dict[str, Any]],
    hyperstack_pricebook: list[dict[str, Any]],
) -> None:
    snaps = parse_hyperstack(hyperstack_flavors, hyperstack_pricebook, _TS)
    assert all(s.snapshotted_at == _TS for s in snaps)


def test_parse_hyperstack_handles_empty_groups() -> None:
    assert parse_hyperstack([], [], _TS) == []


# -- fetch_hyperstack (mocked network) -----------------------------------------


def test_fetch_hyperstack_calls_both_endpoints_and_joins(
    patch_hyperstack_network: Any,
    hyperstack_flavors: list[dict[str, Any]],
    hyperstack_pricebook: list[dict[str, Any]],
) -> None:
    patch_hyperstack_network(hyperstack_flavors, hyperstack_pricebook)
    snaps = fetch_hyperstack("dummy-key", _TS)
    assert len(snaps) == 4
    assert all(s.source == "hyperstack" for s in snaps)


def test_fetch_hyperstack_returns_empty_on_network_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise(*a: Any, **k: Any) -> None:
        raise OSError("network down")

    monkeypatch.setattr(hyperstack.requests, "get", _raise)
    assert fetch_hyperstack("dummy-key", _TS) == []


def test_fetch_hyperstack_returns_empty_on_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from core.ingestion.providers.tests.conftest import FakeResponse

    class BadResponse(FakeResponse):
        def raise_for_status(self) -> None:
            raise Exception("HTTP 401")

    monkeypatch.setattr(hyperstack.requests, "get", lambda *a, **k: BadResponse({}))
    assert fetch_hyperstack("dummy-key", _TS) == []


def test_fetch_hyperstack_handles_non_dict_pricebook_response(
    monkeypatch: pytest.MonkeyPatch,
    hyperstack_flavors: list[dict[str, Any]],
) -> None:
    """If the pricebook returns null, we return [] without an exception (both calls happen)."""
    from core.ingestion.providers.tests.conftest import FakeResponse

    call_count = 0

    def _fake_get(url: str, *a: Any, **k: Any) -> FakeResponse:
        nonlocal call_count
        call_count += 1
        if "pricebook" in str(url):
            return FakeResponse(None)
        return FakeResponse({"data": hyperstack_flavors})

    monkeypatch.setattr(hyperstack.requests, "get", _fake_get)
    assert fetch_hyperstack("dummy-key", _TS) == []
    assert call_count == 2
