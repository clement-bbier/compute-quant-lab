"""Tests du connecteur TensorDock : parser robuste, hostnodes v2, cas dégénérés.

Patron TDD : on appelle ``parse_tensordock`` directement (zéro réseau) et on vérifie
les ``Snapshot`` produits. Les tests réseau utilisent ``patch_tensordock_network`` (conftest).

Endpoint retenu : ``GET https://dashboard.tensordock.com/api/v2/hostnodes``
  (retourne 403 sans auth — confirme que l'endpoint existe).

Schéma par nœud (à confirmer en live) :
  ``specs.gpu.{amount, type, price}`` où ``price`` = $/GPU·h (hypothèse).
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest

from core.ingestion.providers import tensordock
from core.ingestion.providers.tensordock import (
    _hostnodes_records,
    fetch_tensordock,
    parse_tensordock,
)

_TS = dt.datetime(2026, 6, 23, tzinfo=dt.timezone.utc)


# ── _hostnodes_records ────────────────────────────────────────────────────────


def test_hostnodes_records_accepts_list(
    tensordock_hostnodes: list[dict[str, Any]],
) -> None:
    result = _hostnodes_records({"hostnodes": tensordock_hostnodes})
    assert result == tensordock_hostnodes


def test_hostnodes_records_accepts_dict_mapping(
    tensordock_hostnodes: list[dict[str, Any]],
) -> None:
    as_dict = {node["id"]: node for node in tensordock_hostnodes}
    result = _hostnodes_records({"hostnodes": as_dict})
    assert result == list(as_dict.values())


def test_hostnodes_records_missing_key_returns_empty() -> None:
    assert _hostnodes_records({}) == []


def test_hostnodes_records_unexpected_type_returns_empty() -> None:
    assert _hostnodes_records({"hostnodes": "not-a-list"}) == []


def test_hostnodes_records_reads_data_envelope(
    tensordock_hostnodes: list[dict[str, Any]],
) -> None:
    """Enveloppe v2 réelle (vérifiée en live) : ``{"data": {"hostnodes": [...]}}``."""
    result = _hostnodes_records({"data": {"hostnodes": tensordock_hostnodes}})
    assert result == tensordock_hostnodes


# ── parse_tensordock ──────────────────────────────────────────────────────────


def test_parse_tensordock_happy_path(
    tensordock_hostnodes: list[dict[str, Any]],
) -> None:
    snaps = parse_tensordock(tensordock_hostnodes, _TS)
    assert len(snaps) == 2
    by_model = {s.gpu_model: s for s in snaps}
    assert by_model["H100"].price_usd_per_hour == 2.80
    assert by_model["H100"].availability == 4
    assert by_model["RTX4090"].price_usd_per_hour == 0.45
    assert by_model["RTX4090"].availability == 2


def test_parse_tensordock_populates_region_and_vram(
    tensordock_hostnodes: list[dict[str, Any]],
) -> None:
    snaps = parse_tensordock(tensordock_hostnodes, _TS)
    h100 = next(s for s in snaps if s.gpu_model == "H100")
    assert h100.region == "us-east"  # location.region
    assert h100.gpu_memory_gb == 80.0  # specs.gpu.vram


def test_parse_tensordock_skips_zero_amount(
    tensordock_hostnodes: list[dict[str, Any]],
) -> None:
    snaps = parse_tensordock(tensordock_hostnodes, _TS)
    # hn-3 a amount=0 → écarté
    assert all(s.availability > 0 for s in snaps)


def test_parse_tensordock_skips_zero_price() -> None:
    nodes = [
        {"id": "x", "specs": {"gpu": {"amount": 4, "type": "A100", "price": 0.0}}},
    ]
    assert parse_tensordock(nodes, _TS) == []


def test_parse_tensordock_skips_negative_price() -> None:
    nodes = [
        {"id": "x", "specs": {"gpu": {"amount": 2, "type": "H100", "price": -1.5}}},
    ]
    assert parse_tensordock(nodes, _TS) == []


def test_parse_tensordock_skips_missing_specs() -> None:
    nodes = [{"id": "x"}]
    assert parse_tensordock(nodes, _TS) == []


def test_parse_tensordock_skips_none_specs() -> None:
    nodes = [{"id": "x", "specs": None}]
    assert parse_tensordock(nodes, _TS) == []


def test_parse_tensordock_skips_non_dict_gpu() -> None:
    nodes = [{"id": "x", "specs": {"gpu": "not-a-dict"}}]
    assert parse_tensordock(nodes, _TS) == []


def test_parse_tensordock_skips_non_dict_node() -> None:
    # L'enveloppe peut contenir des entrées corrompues
    nodes: list[Any] = ["not-a-dict", None, 42]
    assert parse_tensordock(nodes, _TS) == []


def test_parse_tensordock_source_and_lease_type(
    tensordock_hostnodes: list[dict[str, Any]],
) -> None:
    snaps = parse_tensordock(tensordock_hostnodes, _TS)
    assert all(s.source == "tensordock" for s in snaps)
    assert all(s.lease_type == "on_demand" for s in snaps)


def test_parse_tensordock_snapshotted_at_preserved(
    tensordock_hostnodes: list[dict[str, Any]],
) -> None:
    snaps = parse_tensordock(tensordock_hostnodes, _TS)
    assert all(s.snapshotted_at == _TS for s in snaps)


def test_parse_tensordock_handles_amount_as_string() -> None:
    """``amount`` peut être une chaîne dans certaines implémentations."""
    nodes = [
        {"id": "x", "specs": {"gpu": {"amount": "4", "type": "H100", "price": 2.5}}},
    ]
    snaps = parse_tensordock(nodes, _TS)
    assert len(snaps) == 1
    assert snaps[0].availability == 4


def test_parse_tensordock_empty_list_returns_empty() -> None:
    assert parse_tensordock([], _TS) == []


def test_parse_tensordock_normalizes_gpu_type() -> None:
    """Le champ ``type`` (ex. ``'h100-sxm5-80gb'``) est normalisé en ``'H100'``."""
    nodes = [
        {"id": "y", "specs": {"gpu": {"amount": 1, "type": "h100-sxm5-80gb", "price": 3.0}}},
    ]
    snaps = parse_tensordock(nodes, _TS)
    assert snaps[0].gpu_model == "H100"


# ── fetch_tensordock (réseau mocké) ──────────────────────────────────────────


def test_fetch_tensordock_happy_path(
    patch_tensordock_network: Any,
    tensordock_hostnodes: list[dict[str, Any]],
) -> None:
    patch_tensordock_network(tensordock_hostnodes)
    snaps = fetch_tensordock("dummy-key", _TS)
    assert len(snaps) == 2
    assert all(s.source == "tensordock" for s in snaps)


def test_fetch_tensordock_returns_empty_on_network_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise(*a: Any, **k: Any) -> None:
        raise OSError("network down")

    monkeypatch.setattr(tensordock.requests, "get", _raise)
    snaps = fetch_tensordock("dummy-key", _TS)
    assert snaps == []


def test_fetch_tensordock_returns_empty_on_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from core.ingestion.providers.tests.conftest import FakeResponse

    class BadResponse(FakeResponse):
        def raise_for_status(self) -> None:
            raise Exception("HTTP 403")

    monkeypatch.setattr(tensordock.requests, "get", lambda *a, **k: BadResponse({}))
    snaps = fetch_tensordock("dummy-key", _TS)
    assert snaps == []


def test_fetch_tensordock_returns_empty_on_non_dict_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from core.ingestion.providers.tests.conftest import FakeResponse

    monkeypatch.setattr(tensordock.requests, "get", lambda *a, **k: FakeResponse([]))
    snaps = fetch_tensordock("dummy-key", _TS)
    assert snaps == []


def test_fetch_tensordock_uses_bearer_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vérifie que l'auth Bearer est bien envoyée dans les headers."""
    captured: dict[str, Any] = {}
    from core.ingestion.providers.tests.conftest import FakeResponse

    def _capture(
        url: str, *a: Any, headers: dict[str, str] | None = None, **k: Any
    ) -> FakeResponse:
        captured["headers"] = headers or {}
        return FakeResponse({"hostnodes": []})

    monkeypatch.setattr(tensordock.requests, "get", _capture)
    fetch_tensordock("my-secret-key", _TS)
    assert captured["headers"].get("Authorization") == "Bearer my-secret-key"
