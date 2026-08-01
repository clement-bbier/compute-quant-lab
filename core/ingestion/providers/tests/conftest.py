"""Deterministic fixtures for the ``providers`` package tests (zero network).

Follows the lab's conftest pattern (``core/storage/tests``, ``core/features/tests``):
fixtures returning either data or *factories*, with no inter-test imports (the ``tests/``
directory is not a package). Every network call is mocked; no live API is contacted. The
payloads reproduce the real shape of the Vast.ai (bundles) and RunPod (``gpuTypes``) APIs.
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Callable

import pytest

#: Frozen observation timestamp (UTC tz-aware), shared by the parity golden cases.
NOW = dt.datetime(2026, 6, 21, tzinfo=dt.timezone.utc)


class FakeResponse:
    """Fake HTTP response: exposes ``raise_for_status`` and ``json`` (zero network).

    ``payload`` is typed ``Any``: some venues return a JSON object (Vast.ai
    ``{"offers": ...}``) and others a **bare array** (DataCrunch ``/instance-types``).
    """

    def __init__(self, payload: Any) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> Any:
        return self._payload


@pytest.fixture
def now() -> dt.datetime:
    """Frozen snapshot instant (UTC tz-aware)."""
    return NOW


@pytest.fixture
def vastai_offers() -> list[dict[str, Any]]:
    """Sample Vast.ai offers (real shape of the bundles API)."""
    return [
        {"gpu_name": "H100 SXM", "dph_total": 16.0, "num_gpus": 8, "rentable": True},
        {"gpu_name": "A100 PCIE", "dph_total": 4.0, "num_gpus": 4, "rentable": True},
        {"gpu_name": "H100 SXM", "dph_total": 2.0, "num_gpus": 1, "rentable": False},
    ]


@pytest.fixture
def runpod_gpu_types() -> list[dict[str, Any]]:
    """Sample RunPod GPU types (real ``gpuTypes`` shape: secure + community)."""
    return [
        {"displayName": "A100 PCIe", "securePrice": 1.39, "communityPrice": 1.19},
        {"displayName": "A40", "securePrice": 0, "communityPrice": 0.35},
        {"displayName": "MI300X", "securePrice": None, "communityPrice": None},
    ]


@pytest.fixture
def patch_vastai_network(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[list[dict[str, Any]]], None]:
    """Factory: replaces the Vast.ai network call (``requests.get``) with a fake response."""

    def _patch(offers: list[dict[str, Any]]) -> None:
        from core.ingestion.providers import vastai

        monkeypatch.setattr(
            vastai.requests, "get", lambda *a, **k: FakeResponse({"offers": offers})
        )

    return _patch


@pytest.fixture
def patch_runpod_network(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[list[dict[str, Any]]], None]:
    """Factory: replaces the RunPod network call (``requests.post``) with a fake response."""

    def _patch(gpu_types: list[dict[str, Any]]) -> None:
        from core.ingestion.providers import runpod

        monkeypatch.setattr(
            runpod.requests,
            "post",
            lambda *a, **k: FakeResponse({"data": {"gpuTypes": gpu_types}}),
        )

    return _patch


# -- W2 wave: 5 additional venues (payloads reproducing the real shape of the APIs) --


@pytest.fixture
def primeintellect_items() -> list[dict[str, Any]]:
    """Prime Intellect availability items (aggregator; ``prices.onDemand`` = offer price)."""
    return [
        {
            "cloudId": "ci-1",
            "gpuType": "H100_80GB",
            "provider": "datacrunch",
            "region": "EU",
            "dataCenter": "FIN-01",
            "country": "FI",
            "gpuCount": 8,
            "gpuMemory": 80,
            "stockStatus": "Available",
            "security": "secure",
            "prices": {"onDemand": 24.0, "isVariable": False, "currency": "USD"},
            "isSpot": False,
        },
        {
            "cloudId": "ci-2",
            "gpuType": "A100_80GB",
            "provider": "runpod",
            "region": "US",
            "gpuCount": 4,
            "prices": {"onDemand": 4.0, "isVariable": True, "currency": "USD"},
            "isSpot": True,
        },
        {  # no provider -> bare source "primeintellect"
            "cloudId": "ci-3",
            "gpuType": "RTX4090",
            "gpuCount": 1,
            "prices": {"onDemand": 0.5, "currency": "USD"},
            "isSpot": False,
        },
        {  # 0 GPU -> discarded
            "cloudId": "ci-4",
            "gpuType": "H100",
            "gpuCount": 0,
            "prices": {"onDemand": 3.0},
            "isSpot": False,
        },
        {  # missing/invalid price -> discarded
            "cloudId": "ci-5",
            "gpuType": "L40S",
            "gpuCount": 2,
            "prices": {"onDemand": None},
            "isSpot": False,
        },
    ]


@pytest.fixture
def datacrunch_instance_types() -> list[dict[str, Any]]:
    """DataCrunch ``/instance-types`` catalogue (on-demand + spot machine price, nested specs)."""
    return [
        {
            "id": "it-1",
            "instance_type": "8H100.80S.176V",
            "price_per_hour": "24.0",  # DataCrunch quotes as strings
            "spot_price": "12.0",
            "description": "8x H100 SXM5 80GB",
            "cpu": {"description": "176 CPU", "number_of_cores": 176},
            "gpu": {"description": "8x H100 SXM5 80GB", "number_of_gpus": 8},
            "memory": {"description": "1480GB RAM", "size_in_gigabytes": 1480},
            "gpu_memory": {"description": "640GB", "size_in_gigabytes": 640},
            "storage": {"description": "2048GB NVMe", "size_in_gigabytes": 2048},
        },
        {  # spot 0 -> only the on-demand one is emitted
            "id": "it-2",
            "instance_type": "1A100.22V",
            "price_per_hour": "1.20",
            "spot_price": "0",
            "gpu": {"description": "1x A100 SXM4 40GB", "number_of_gpus": 1},
        },
        {  # CPU instance (0 GPU) -> discarded
            "id": "it-3",
            "instance_type": "CPU.4V",
            "price_per_hour": "0.10",
            "spot_price": "0.05",
            "gpu": {"description": "", "number_of_gpus": 0},
        },
    ]


@pytest.fixture
def cudo_machine_types() -> list[dict[str, Any]]:
    """CUDO machine types (``gpuPriceHr.value`` is **already** a $/GPU·h price, as a string)."""
    return [
        {
            "machineType": "h100",
            "gpuModel": "NVIDIA H100 80GB HBM3",
            "gpuModelId": "nvidia-h100-80gb",
            "dataCenterId": "no-luster-1",
            "gpuPriceHr": {"value": "2.50", "currency": "usd"},
            "vcpuPriceHr": {"value": "0.002", "currency": "usd"},
            "memoryGibPriceHr": {"value": "0.001", "currency": "usd"},
            "totalGpuFree": 16,
            "gpuMemoryGib": 80,
        },
        {
            "machineType": "a40",
            "gpuModel": "NVIDIA A40",
            "gpuModelId": "nvidia-a40",
            "dataCenterId": "se-smedjebacken-1",
            "gpuPriceHr": {"value": "0.45", "currency": "usd"},
            "totalGpuFree": 3,
        },
        {  # no GPU model / zero price -> discarded
            "machineType": "cpu-epyc",
            "gpuModel": "",
            "gpuPriceHr": {"value": "0", "currency": "usd"},
            "totalGpuFree": 0,
        },
    ]


@pytest.fixture
def hyperstack_flavors() -> list[dict[str, Any]]:
    """Hyperstack ``/v1/core/flavors`` flavor groups (real schema: WITHOUT prices).

    The price lives in the separate pricebook. Join: ``flavor.gpu`` (**GPU type**, e.g.
    ``"H100-80G-PCIe"``) against ``pricebook.name``. The ``-spot`` suffix of the type = spot
    lease. A100-80G-SXM4 is present here but absent from the pricebook -> discarded
    (non-match).
    """
    return [
        {
            "gpu": "H100-80G-PCIe",
            "region_name": "CANADA-1",
            "flavors": [
                {
                    "id": 101,
                    "name": "n3-H100x8",
                    "gpu": "H100-80G-PCIe",
                    "gpu_count": 8,
                    "region_name": "CANADA-1",
                    "cpu": 192,
                    "ram": 1800,
                    "disk": 32000,
                    "stock_available": True,
                },
                {
                    "id": 102,
                    "name": "n3-H100x1",
                    "gpu": "H100-80G-PCIe",
                    "gpu_count": 1,
                    "region_name": "CANADA-1",
                    "cpu": 28,
                    "ram": 180,
                    "disk": 100,
                    "stock_available": True,
                },
            ],
        },
        {
            "gpu": "H100-80G-PCIe-spot",
            "region_name": "CANADA-1",
            "flavors": [
                {
                    "id": 110,
                    "name": "n3-H100x1-spot",
                    "gpu": "H100-80G-PCIe-spot",
                    "gpu_count": 1,
                    "region_name": "CANADA-1",
                    "cpu": 28,
                    "ram": 180,
                    "disk": 100,
                    "stock_available": True,
                },
            ],
        },
        {
            "gpu": "L40",
            "region_name": "NORWAY-1",
            "flavors": [
                {
                    "id": 201,
                    "name": "n3-L40x1",
                    "gpu": "L40",
                    "gpu_count": 1,
                    "region_name": "NORWAY-1",
                    "cpu": 16,
                    "ram": 60,
                    "disk": 100,
                    "stock_available": False,
                },
                {  # CPU flavor (0 GPU) -> discarded
                    "id": 301,
                    "name": "cpu-small",
                    "gpu": None,
                    "gpu_count": 0,
                    "stock_available": True,
                },
            ],
        },
        {  # A100 in flavors but ABSENT from the pricebook -> discarded (non-match test)
            "gpu": "A100-80G-SXM4",
            "region_name": "US-1",
            "flavors": [
                {
                    "id": 401,
                    "name": "n3-A100-SXM4x8",
                    "gpu": "A100-80G-SXM4",
                    "gpu_count": 8,
                    "region_name": "US-1",
                    "cpu": 192,
                    "ram": 1900,
                    "disk": 20000,
                    "stock_available": True,
                },
            ],
        },
    ]


@pytest.fixture
def hyperstack_pricebook() -> list[dict[str, Any]]:
    """Hyperstack ``/v1/pricebook`` (real schema: per component, ``value`` = STRING).

    ``name`` = GPU type (+ vCPU/RAM/inference models, never joined); ``value`` = price
    **already per GPU and per hour** as a string (e.g. ``"1.9"``, ``"0E-9"`` for zero).
    """
    return [
        {"id": 1, "name": "vCPU", "value": "0E-9"},  # zero component -> ignored
        {"id": 2, "name": "RAM", "value": "0.0015"},  # non-GPU component -> never joined
        {"id": 3, "name": "H100-80G-PCIe", "value": "1.9", "original_value": "1.9"},
        {"id": 4, "name": "H100-80G-PCIe-spot", "value": "1.52"},
        {"id": 5, "name": "L40", "value": "0.99"},
        {"id": 6, "name": "deepseek-ai/DeepSeek-R1 (output)", "value": "2.55"},  # inference
    ]


@pytest.fixture
def tensordock_hostnodes() -> list[dict[str, Any]]:
    """TensorDock v2 hostnodes (``specs.gpu.price`` = $/GPU·h price; ``amount`` = stock)."""
    return [
        {
            "id": "hn-1",
            "status": "online",
            "location": {"country": "United States", "region": "us-east", "city": "NYC"},
            "specs": {
                "gpu": {"amount": 4, "type": "h100-sxm5-80gb", "vram": 80, "price": 2.80},
                "cpu": {"amount": 64, "price": 0.01},
                "ram": {"amount": 256, "price": 0.005},
                "storage": {"amount": 4000, "price": 0.0001},
            },
        },
        {
            "id": "hn-2",
            "status": "online",
            "location": {"country": "Germany", "region": "eu-central", "city": "Frankfurt"},
            "specs": {"gpu": {"amount": 2, "type": "rtx4090-24gb", "vram": 24, "price": 0.45}},
        },
        {  # no GPU available any more -> discarded
            "id": "hn-3",
            "status": "offline",
            "specs": {"gpu": {"amount": 0, "type": "", "price": 0.0}},
        },
    ]


@pytest.fixture
def patch_primeintellect_network(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[list[dict[str, Any]]], None]:
    """Factory: replaces the Prime Intellect network call (``requests.get``)."""

    def _patch(items: list[dict[str, Any]]) -> None:
        from core.ingestion.providers import primeintellect

        monkeypatch.setattr(
            primeintellect.requests,
            "get",
            lambda *a, **k: FakeResponse({"items": items, "totalCount": len(items)}),
        )

    return _patch


@pytest.fixture
def patch_datacrunch_network(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[list[dict[str, Any]]], None]:
    """Factory: replaces the OAuth2 token (``requests.post``) and the catalogue (``requests.get``)."""

    def _patch(instance_types: list[dict[str, Any]]) -> None:
        from core.ingestion.providers import datacrunch

        monkeypatch.setattr(
            datacrunch.requests,
            "post",
            lambda *a, **k: FakeResponse({"access_token": "tok", "token_type": "Bearer"}),
        )
        monkeypatch.setattr(
            datacrunch.requests, "get", lambda *a, **k: FakeResponse(instance_types)
        )

    return _patch


@pytest.fixture
def patch_cudo_network(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[list[dict[str, Any]]], None]:
    """Factory: replaces the CUDO network call (``requests.get``)."""

    def _patch(machine_types: list[dict[str, Any]]) -> None:
        from core.ingestion.providers import cudo

        monkeypatch.setattr(
            cudo.requests, "get", lambda *a, **k: FakeResponse({"machineTypes": machine_types})
        )

    return _patch


@pytest.fixture
def patch_hyperstack_network(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[list[dict[str, Any]], list[dict[str, Any]]], None]:
    """Factory: replaces both Hyperstack network calls (flavors + pricebook).

    ``fetch_hyperstack`` calls ``/v1/core/flavors`` then ``/v1/pricebook`` in turn. We route by
    URL: the URL containing ``/pricebook`` gets the pricebook, the others get the flavors
    response.
    """

    def _patch(flavor_groups: list[dict[str, Any]], pricebook: list[dict[str, Any]]) -> None:
        from core.ingestion.providers import hyperstack

        def _fake_get(url: str, *a: Any, **k: Any) -> FakeResponse:
            if "pricebook" in str(url):
                return FakeResponse(pricebook)
            return FakeResponse({"data": flavor_groups})

        monkeypatch.setattr(hyperstack.requests, "get", _fake_get)

    return _patch


@pytest.fixture
def patch_tensordock_network(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[list[dict[str, Any]]], None]:
    """Factory: replaces the TensorDock network call (``requests.get``)."""

    def _patch(hostnodes: list[dict[str, Any]]) -> None:
        from core.ingestion.providers import tensordock

        # Real v2 envelope: everything sits under "data".
        monkeypatch.setattr(
            tensordock.requests,
            "get",
            lambda *a, **k: FakeResponse({"data": {"hostnodes": hostnodes}}),
        )

    return _patch
