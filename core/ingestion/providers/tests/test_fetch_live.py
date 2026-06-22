"""``fetch_live_gpu_prices`` (cible du collecteur prod) : comportement INCHANGÉ.

Garde-fou de non-régression de l'entrée publique appelée par
``infra/collectors/gpu_price_snapshot.py`` : agrégation des venues actives, défaut ``now``
en UTC tz-aware partagé, et ``RuntimeError`` si aucune source n'est configurée.
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Callable

import pytest

from core.ingestion.gpu_market import fetch_live_gpu_prices


def test_fetch_live_aggregates_active_providers_and_defaults_now(
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

    snaps = fetch_live_gpu_prices()  # now=None -> utcnow

    assert {s.source for s in snaps} == {"vastai", "runpod"}
    instants = {s.snapshotted_at for s in snaps}
    assert len(instants) == 1  # un seul `now` partagé par toutes les venues
    ts = next(iter(instants))
    assert ts.tzinfo is not None and ts.utcoffset() == dt.timedelta(0)  # UTC tz-aware


def test_fetch_live_uses_explicit_now(
    now: dt.datetime,
    monkeypatch: pytest.MonkeyPatch,
    patch_vastai_network: Callable[[list[dict[str, Any]]], None],
    vastai_offers: list[dict[str, Any]],
) -> None:
    monkeypatch.setenv("VASTAI_API_KEY", "x")
    monkeypatch.delenv("RUNPOD_API_KEY", raising=False)
    patch_vastai_network(vastai_offers)

    snaps = fetch_live_gpu_prices(now)

    assert snaps and all(s.snapshotted_at == now for s in snaps)


def test_fetch_live_raises_when_nothing_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VASTAI_API_KEY", raising=False)
    monkeypatch.delenv("RUNPOD_API_KEY", raising=False)

    with pytest.raises(RuntimeError):
        fetch_live_gpu_prices()
