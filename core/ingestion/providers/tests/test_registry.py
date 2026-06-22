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


def test_providers_expose_the_protocol_surface() -> None:
    assert {p.name for p in PROVIDERS} == {"vastai", "runpod"}
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
