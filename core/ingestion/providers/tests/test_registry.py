"""Registre pluggable : agrégation, key-gating et skip sans clé (réseau mocké).

Le registre n'appelle un provider que si **toutes** ses ``required_env`` sont présentes ;
sinon il loggue un avertissement et le saute (comportement historique de
``fetch_live_gpu_prices``). Les tests contrôlent l'environnement via ``monkeypatch`` pour
rester hermétiques (le worktree n'a pas de ``.env``).
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any, Callable

import pytest

from core.ingestion.providers import PROVIDERS, fetch_all

#: Toutes les clés d'environnement des venues enregistrées (gate du registre). Purgées
#: avant chaque test pour rester hermétique : un ``.env`` ambiant ne doit pas influer.
_ALL_PROVIDER_KEYS = (
    "VASTAI_API_KEY",
    "RUNPOD_API_KEY",
    "PRIMEINTELLECT_API_KEY",
    "DATACRUNCH_CLIENT_ID",
    "DATACRUNCH_CLIENT_SECRET",
    "CUDO_API_KEY",
    "HYPERSTACK_API_KEY",
    "TENSORDOCK_API_KEY",
)


@pytest.fixture(autouse=True)
def _clear_provider_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """Environnement vierge de toute clé venue avant chaque test (déterminisme)."""
    for key in _ALL_PROVIDER_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_providers_expose_the_protocol_surface() -> None:
    assert {p.name for p in PROVIDERS} == {
        "vastai",
        "runpod",
        "primeintellect",
        "datacrunch",
        "cudo",
        "hyperstack",
        "tensordock",
    }
    for p in PROVIDERS:
        assert p.required_env  # au moins une clé requise
        assert callable(p.fetch)


def test_fetch_all_skips_providers_without_key(
    now: dt.datetime, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.delenv("VASTAI_API_KEY", raising=False)
    monkeypatch.delenv("RUNPOD_API_KEY", raising=False)

    with caplog.at_level(logging.WARNING):
        snaps = fetch_all(now)

    assert snaps == []
    assert "VASTAI_API_KEY" in caplog.text
    assert "RUNPOD_API_KEY" in caplog.text


def test_fetch_all_is_key_gated(
    now: dt.datetime,
    monkeypatch: pytest.MonkeyPatch,
    patch_vastai_network: Callable[[list[dict[str, Any]]], None],
    vastai_offers: list[dict[str, Any]],
) -> None:
    monkeypatch.setenv("VASTAI_API_KEY", "x")
    monkeypatch.delenv("RUNPOD_API_KEY", raising=False)
    patch_vastai_network(vastai_offers)

    snaps = fetch_all(now)

    assert {s.source for s in snaps} == {"vastai"}  # runpod sauté faute de clé


def test_fetch_all_aggregates_active_providers_in_order(
    now: dt.datetime,
    monkeypatch: pytest.MonkeyPatch,
    patch_vastai_network: Callable[[list[dict[str, Any]]], None],
    patch_runpod_network: Callable[[list[dict[str, Any]]], None],
    vastai_offers: list[dict[str, Any]],
    runpod_gpu_types: list[dict[str, Any]],
) -> None:
    monkeypatch.setenv("VASTAI_API_KEY", "x")
    monkeypatch.setenv("RUNPOD_API_KEY", "y")
    patch_vastai_network(vastai_offers)
    patch_runpod_network(runpod_gpu_types)

    snaps = fetch_all(now)

    assert {s.source for s in snaps} == {"vastai", "runpod"}
    assert len(snaps) == 4  # 2 vastai (rentables) + 2 runpod (prix valides)
    assert snaps[0].source == "vastai"  # ordre du registre préservé
    assert snaps[-1].source == "runpod"


def test_fetch_all_includes_active_w2_venue(
    now: dt.datetime,
    monkeypatch: pytest.MonkeyPatch,
    patch_cudo_network: Callable[[list[dict[str, Any]]], None],
    cudo_machine_types: list[dict[str, Any]],
) -> None:
    # Une venue W2 (CUDO) doit transiter par le registre dès que sa clé est présente,
    # sans qu'aucune autre couche ne change (les venues sans clé restent sautées).
    monkeypatch.setenv("CUDO_API_KEY", "k")
    patch_cudo_network(cudo_machine_types)

    snaps = fetch_all(now)

    assert {s.source for s in snaps} == {"cudo"}
    assert len(snaps) == 2  # 2 types de machine GPU valides
