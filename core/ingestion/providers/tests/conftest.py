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
    """Réponse HTTP factice : expose ``raise_for_status`` et ``json`` (zéro réseau)."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
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
