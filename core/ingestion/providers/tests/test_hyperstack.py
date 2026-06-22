"""Tests du connecteur Hyperstack : double appel (flavors + pricebook), jointure, robustesse.

Patron TDD : on appelle ``parse_hyperstack`` directement (zéro réseau) et on vérifie
les ``Snapshot`` produits — jointure correcte, division par gpu_count, exclusions,
cas dégénérés. Les tests réseau utilisent ``patch_hyperstack_network`` (conftest).
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest

from core.ingestion.providers import hyperstack
from core.ingestion.providers.hyperstack import (
    _build_price_index,
    fetch_hyperstack,
    parse_hyperstack,
)

_TS = dt.datetime(2026, 6, 23, tzinfo=dt.timezone.utc)


# ── _build_price_index ────────────────────────────────────────────────────────


def test_build_price_index_filters_invalid_entries() -> None:
    pricebook: list[dict[str, Any]] = [
        {"name": "flavor-a", "value": 5.0},
        {"name": "flavor-b", "value": 0},  # valeur nulle → ignorée
        {"name": "flavor-c", "value": -1.0},  # valeur négative → ignorée
        {"name": None, "value": 2.0},  # pas de nom → ignorée
        {"value": 3.0},  # clé name absente → ignorée
        {"name": "flavor-d", "value": 1.5},
    ]
    idx = _build_price_index(pricebook)
    assert idx == {"flavor-a": 5.0, "flavor-d": 1.5}


def test_build_price_index_accepts_int_value() -> None:
    pricebook = [{"name": "flavor-x", "value": 10}]
    assert _build_price_index(pricebook) == {"flavor-x": 10.0}


# ── parse_hyperstack ──────────────────────────────────────────────────────────


def test_parse_hyperstack_join_and_per_gpu_division(
    hyperstack_flavors: list[dict[str, Any]],
    hyperstack_pricebook: list[dict[str, Any]],
) -> None:
    snaps = parse_hyperstack(hyperstack_flavors, hyperstack_pricebook, _TS)
    assert len(snaps) == 3
    by_name = {s.gpu_model: s for s in snaps}
    assert "H100" in by_name
    assert "L40" in by_name
    # n3-H100x8 : 27.92 / 8 = 3.49
    h100_multi = next(s for s in snaps if s.gpu_model == "H100" and s.availability == 1)
    assert abs(h100_multi.price_usd_per_hour - 27.92 / 8) < 1e-9
    # n3-H100x1 : 3.49 / 1 = 3.49
    h100_single = next(
        s
        for s in snaps
        if s.gpu_model == "H100" and s.availability == 1 and abs(s.price_usd_per_hour - 3.49) < 1e-9
    )
    assert h100_single.lease_type == "on_demand"


def test_parse_hyperstack_stock_available_false_gives_zero_availability(
    hyperstack_flavors: list[dict[str, Any]],
    hyperstack_pricebook: list[dict[str, Any]],
) -> None:
    snaps = parse_hyperstack(hyperstack_flavors, hyperstack_pricebook, _TS)
    l40 = next(s for s in snaps if s.gpu_model == "L40")
    assert l40.availability == 0


def test_parse_hyperstack_skips_zero_gpu_count(
    hyperstack_pricebook: list[dict[str, Any]],
) -> None:
    groups = [
        {
            "gpu": "A100",
            "flavors": [
                {"name": "cpu-small", "gpu": None, "gpu_count": 0, "stock_available": True}
            ],
        }
    ]
    snaps = parse_hyperstack(groups, hyperstack_pricebook, _TS)
    assert snaps == []


def test_parse_hyperstack_empty_pricebook_returns_empty(
    hyperstack_flavors: list[dict[str, Any]],
) -> None:
    snaps = parse_hyperstack(hyperstack_flavors, [], _TS)
    assert snaps == []


def test_parse_hyperstack_no_matching_name_returns_empty(
    hyperstack_flavors: list[dict[str, Any]],
) -> None:
    pricebook = [{"name": "unknown-flavor", "value": 99.0}]
    snaps = parse_hyperstack(hyperstack_flavors, pricebook, _TS)
    assert snaps == []


def test_parse_hyperstack_source_is_hyperstack(
    hyperstack_flavors: list[dict[str, Any]],
    hyperstack_pricebook: list[dict[str, Any]],
) -> None:
    snaps = parse_hyperstack(hyperstack_flavors, hyperstack_pricebook, _TS)
    assert all(s.source == "hyperstack" for s in snaps)


def test_parse_hyperstack_snapshotted_at_preserved(
    hyperstack_flavors: list[dict[str, Any]],
    hyperstack_pricebook: list[dict[str, Any]],
) -> None:
    snaps = parse_hyperstack(hyperstack_flavors, hyperstack_pricebook, _TS)
    assert all(s.snapshotted_at == _TS for s in snaps)


def test_parse_hyperstack_handles_empty_groups() -> None:
    snaps = parse_hyperstack([], [], _TS)
    assert snaps == []


def test_parse_hyperstack_handles_malformed_flavor_no_name(
    hyperstack_pricebook: list[dict[str, Any]],
) -> None:
    """Un flavor sans ``name`` ne doit pas lever d'exception."""
    groups = [
        {
            "gpu": "H100",
            "flavors": [{"gpu_count": 1, "stock_available": True}],  # pas de name
        }
    ]
    snaps = parse_hyperstack(groups, hyperstack_pricebook, _TS)
    assert snaps == []  # nom absent → pas dans price_index → écarté proprement


def test_parse_hyperstack_handles_pricebook_enveloped_in_data() -> None:
    """``value`` doit être extrait correctement même avec pricebook comme liste plate."""
    flavor_groups = [
        {
            "gpu": "A100",
            "flavors": [
                {
                    "id": 1,
                    "name": "n1-A100x2",
                    "gpu": "A100",
                    "gpu_count": 2,
                    "stock_available": True,
                }
            ],
        }
    ]
    pricebook = [{"id": 10, "name": "n1-A100x2", "value": 6.0, "original_value": 6.0}]
    snaps = parse_hyperstack(flavor_groups, pricebook, _TS)
    assert len(snaps) == 1
    assert snaps[0].price_usd_per_hour == 3.0  # 6.0 / 2


# ── fetch_hyperstack (réseau mocké) ──────────────────────────────────────────


def test_fetch_hyperstack_calls_both_endpoints_and_joins(
    patch_hyperstack_network: Any,
    hyperstack_flavors: list[dict[str, Any]],
    hyperstack_pricebook: list[dict[str, Any]],
) -> None:
    patch_hyperstack_network(hyperstack_flavors, hyperstack_pricebook)
    snaps = fetch_hyperstack("dummy-key", _TS)
    assert len(snaps) == 3
    assert all(s.source == "hyperstack" for s in snaps)


def test_fetch_hyperstack_returns_empty_on_network_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise(*a: Any, **k: Any) -> None:
        raise OSError("network down")

    monkeypatch.setattr(hyperstack.requests, "get", _raise)
    snaps = fetch_hyperstack("dummy-key", _TS)
    assert snaps == []


def test_fetch_hyperstack_returns_empty_on_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from core.ingestion.providers.tests.conftest import FakeResponse

    class BadResponse(FakeResponse):
        def raise_for_status(self) -> None:
            raise Exception("HTTP 401")

    monkeypatch.setattr(hyperstack.requests, "get", lambda *a, **k: BadResponse({}))
    snaps = fetch_hyperstack("dummy-key", _TS)
    assert snaps == []


def test_fetch_hyperstack_handles_non_dict_pricebook_response(
    monkeypatch: pytest.MonkeyPatch,
    hyperstack_flavors: list[dict[str, Any]],
) -> None:
    """Si le pricebook renvoie null/vide, on renvoie [] sans exception."""
    from core.ingestion.providers.tests.conftest import FakeResponse

    call_count = 0

    def _fake_get(url: str, *a: Any, **k: Any) -> FakeResponse:
        nonlocal call_count
        call_count += 1
        if "pricebook" in str(url):
            return FakeResponse(None)
        return FakeResponse({"data": hyperstack_flavors})

    monkeypatch.setattr(hyperstack.requests, "get", _fake_get)
    snaps = fetch_hyperstack("dummy-key", _TS)
    assert snaps == []
    assert call_count == 2  # les 2 appels ont bien eu lieu
