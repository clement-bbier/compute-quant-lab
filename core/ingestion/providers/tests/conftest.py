"""Fixtures déterministes des tests du paquet ``providers`` (zéro réseau).

Patron des conftest du labo (``core/storage/tests``, ``core/features/tests``) : des
fixtures renvoyant des données ou des *factories*, sans import inter-tests (le dossier
``tests/`` n'est pas un package). Tout appel réseau est mocké ; aucune API live n'est
contactée. Les payloads reprennent la forme réelle des API Vast.ai (bundles) et RunPod
(``gpuTypes``).
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Callable

import pytest

#: Horodatage de relevé figé (UTC tz-aware), partagé par les cas-or de parité.
NOW = dt.datetime(2026, 6, 21, tzinfo=dt.timezone.utc)


class FakeResponse:
    """Réponse HTTP factice : expose ``raise_for_status`` et ``json`` (zéro réseau).

    ``payload`` est typé ``Any`` : certaines venues renvoient un objet JSON
    (Vast.ai ``{"offers": …}``) et d'autres un **tableau nu** (DataCrunch
    ``/instance-types``).
    """

    def __init__(self, payload: Any) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> Any:
        return self._payload


@pytest.fixture
def now() -> dt.datetime:
    """Instant de snapshot figé (UTC tz-aware)."""
    return NOW


@pytest.fixture
def vastai_offers() -> list[dict[str, Any]]:
    """Offres Vast.ai d'exemple (forme réelle de l'API bundles)."""
    return [
        {"gpu_name": "H100 SXM", "dph_total": 16.0, "num_gpus": 8, "rentable": True},
        {"gpu_name": "A100 PCIE", "dph_total": 4.0, "num_gpus": 4, "rentable": True},
        {"gpu_name": "H100 SXM", "dph_total": 2.0, "num_gpus": 1, "rentable": False},
    ]


@pytest.fixture
def runpod_gpu_types() -> list[dict[str, Any]]:
    """Types GPU RunPod d'exemple (forme réelle ``gpuTypes`` : secure + community)."""
    return [
        {"displayName": "A100 PCIe", "securePrice": 1.39, "communityPrice": 1.19},
        {"displayName": "A40", "securePrice": 0, "communityPrice": 0.35},
        {"displayName": "MI300X", "securePrice": None, "communityPrice": None},
    ]


@pytest.fixture
def patch_vastai_network(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[list[dict[str, Any]]], None]:
    """Factory : remplace l'appel réseau Vast.ai (``requests.get``) par une réponse factice."""

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
    """Factory : remplace l'appel réseau RunPod (``requests.post``) par une réponse factice."""

    def _patch(gpu_types: list[dict[str, Any]]) -> None:
        from core.ingestion.providers import runpod

        monkeypatch.setattr(
            runpod.requests,
            "post",
            lambda *a, **k: FakeResponse({"data": {"gpuTypes": gpu_types}}),
        )

    return _patch


# ── Vague W2 : 5 venues supplémentaires (payloads reprenant la forme réelle des API) ──


@pytest.fixture
def primeintellect_items() -> list[dict[str, Any]]:
    """Items d'availability Prime Intellect (agrégateur ; ``prices.onDemand`` = prix offre)."""
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
        {  # pas de provider → source nue "primeintellect"
            "cloudId": "ci-3",
            "gpuType": "RTX4090",
            "gpuCount": 1,
            "prices": {"onDemand": 0.5, "currency": "USD"},
            "isSpot": False,
        },
        {  # 0 GPU → écarté
            "cloudId": "ci-4",
            "gpuType": "H100",
            "gpuCount": 0,
            "prices": {"onDemand": 3.0},
            "isSpot": False,
        },
        {  # prix absent/invalide → écarté
            "cloudId": "ci-5",
            "gpuType": "L40S",
            "gpuCount": 2,
            "prices": {"onDemand": None},
            "isSpot": False,
        },
    ]


@pytest.fixture
def datacrunch_instance_types() -> list[dict[str, Any]]:
    """Catalogue DataCrunch ``/instance-types`` (prix machine on-demand + spot, specs imbriquées)."""
    return [
        {
            "id": "it-1",
            "instance_type": "8H100.80S.176V",
            "price_per_hour": "24.0",  # DataCrunch cote en chaînes
            "spot_price": "12.0",
            "description": "8x H100 SXM5 80GB",
            "cpu": {"description": "176 CPU", "number_of_cores": 176},
            "gpu": {"description": "8x H100 SXM5 80GB", "number_of_gpus": 8},
            "memory": {"description": "1480GB RAM", "size_in_gigabytes": 1480},
            "gpu_memory": {"description": "640GB", "size_in_gigabytes": 640},
            "storage": {"description": "2048GB NVMe", "size_in_gigabytes": 2048},
        },
        {  # spot 0 → seule l'on-demand est émise
            "id": "it-2",
            "instance_type": "1A100.22V",
            "price_per_hour": "1.20",
            "spot_price": "0",
            "gpu": {"description": "1x A100 SXM4 40GB", "number_of_gpus": 1},
        },
        {  # instance CPU (0 GPU) → écartée
            "id": "it-3",
            "instance_type": "CPU.4V",
            "price_per_hour": "0.10",
            "spot_price": "0.05",
            "gpu": {"description": "", "number_of_gpus": 0},
        },
    ]


@pytest.fixture
def cudo_machine_types() -> list[dict[str, Any]]:
    """Types de machine CUDO (``gpuPriceHr.value`` est **déjà** un prix $/GPU·h, en chaîne)."""
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
        {  # pas de modèle GPU / prix nul → écarté
            "machineType": "cpu-epyc",
            "gpuModel": "",
            "gpuPriceHr": {"value": "0", "currency": "usd"},
            "totalGpuFree": 0,
        },
    ]


@pytest.fixture
def hyperstack_flavors() -> list[dict[str, Any]]:
    """Groupes de flavors Hyperstack ``/v1/core/flavors`` (schéma réel : SANS ``price_per_hour``).

    Le prix vit dans le pricebook séparé ``/v1/pricebook`` ; chaque ``FlavorFields``
    expose uniquement les specs matérielles. Jointure : ``flavor.name`` ↔ ``pricebook.name``.
    """
    return [
        {
            "gpu": "H100",
            "region_name": "NORWAY-1",
            "flavors": [
                {
                    "id": 101,
                    "name": "n3-H100x8",
                    "gpu": "H100",
                    "gpu_count": 8,
                    "cpu": 192,
                    "ram": 1800,
                    "disk": 32000,
                    "stock_available": True,
                },
                {
                    "id": 102,
                    "name": "n3-H100x1",
                    "gpu": "H100",
                    "gpu_count": 1,
                    "stock_available": True,
                },
            ],
        },
        {
            "gpu": "L40",
            "region_name": "CANADA-1",
            "flavors": [
                {
                    "id": 201,
                    "name": "n2-L40x1",
                    "gpu": "L40",
                    "gpu_count": 1,
                    "stock_available": False,
                },
                {  # flavor CPU (0 GPU) → écarté
                    "id": 301,
                    "name": "cpu-small",
                    "gpu": None,
                    "gpu_count": 0,
                    "stock_available": True,
                },
            ],
        },
    ]


@pytest.fixture
def hyperstack_pricebook() -> list[dict[str, Any]]:
    """Pricebook Hyperstack ``/v1/pricebook`` (``value`` = coût horaire machine entière en USD).

    La jointure se fait par ``name`` (= ``FlavorFields.name``). ``value`` est supposé être
    le prix de la machine complète (÷ ``gpu_count`` → $/GPU·h).

    ⚠️ À confirmer en live : ``value`` par machine vs déjà par GPU.
    """
    return [
        {
            "id": 1,
            "name": "n3-H100x8",
            "value": 27.92,
            "original_value": 27.92,
            "discount_applied": False,
            "start_time": None,
            "end_time": None,
        },
        {
            "id": 2,
            "name": "n3-H100x1",
            "value": 3.49,
            "original_value": 3.49,
            "discount_applied": False,
            "start_time": None,
            "end_time": None,
        },
        {
            "id": 3,
            "name": "n2-L40x1",
            "value": 1.00,
            "original_value": 1.00,
            "discount_applied": False,
            "start_time": None,
            "end_time": None,
        },
        {  # cpu-small : gpu_count=0 → écarté par parse_hyperstack
            "id": 4,
            "name": "cpu-small",
            "value": 0.05,
            "original_value": 0.05,
            "discount_applied": False,
            "start_time": None,
            "end_time": None,
        },
    ]


@pytest.fixture
def tensordock_hostnodes() -> list[dict[str, Any]]:
    """Hostnodes TensorDock v2 (``specs.gpu.price`` = prix $/GPU·h ; ``amount`` = stock dispo)."""
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
        {  # plus aucun GPU dispo → écarté
            "id": "hn-3",
            "status": "offline",
            "specs": {"gpu": {"amount": 0, "type": "", "price": 0.0}},
        },
    ]


@pytest.fixture
def patch_primeintellect_network(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[list[dict[str, Any]]], None]:
    """Factory : remplace l'appel réseau Prime Intellect (``requests.get``)."""

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
    """Factory : remplace le token OAuth2 (``requests.post``) et le catalogue (``requests.get``)."""

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
    """Factory : remplace l'appel réseau CUDO (``requests.get``)."""

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
    """Factory : remplace les deux appels réseau Hyperstack (flavors + pricebook).

    ``fetch_hyperstack`` appelle successivement ``/v1/core/flavors`` puis ``/v1/pricebook``.
    On route par URL : l'URL contenant ``/pricebook`` reçoit le pricebook, les autres
    reçoivent la réponse flavors.
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
    """Factory : remplace l'appel réseau TensorDock (``requests.get``)."""

    def _patch(hostnodes: list[dict[str, Any]]) -> None:
        from core.ingestion.providers import tensordock

        monkeypatch.setattr(
            tensordock.requests, "get", lambda *a, **k: FakeResponse({"hostnodes": hostnodes})
        )

    return _patch
