"""Pluggable registry: aggregation, key-gating and skipping without a key (mocked network).

The registry calls a provider only if **all** of its ``required_env`` are present; otherwise it
logs a warning and skips it (the historical behaviour of ``fetch_live_gpu_prices``). The tests
control the environment via ``monkeypatch`` to stay hermetic (the worktree has no ``.env``).
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any, Callable

import pytest

from core.ingestion.providers import PROVIDERS, fetch_all

#: Every environment key of the registered venues (the registry gate). Purged before each
#: test to stay hermetic: an ambient ``.env`` must not have any influence.
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
    """Environment free of any venue key before each test (determinism)."""
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
        assert p.required_env  # at least one required key
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

    assert {s.source for s in snaps} == {"vastai"}  # runpod skipped for lack of a key


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
    assert len(snaps) == 4  # 2 vastai (rentable) + 2 runpod (valid prices)
    assert snaps[0].source == "vastai"  # registry order preserved
    assert snaps[-1].source == "runpod"


def test_fetch_all_includes_active_w2_venue(
    now: dt.datetime,
    monkeypatch: pytest.MonkeyPatch,
    patch_cudo_network: Callable[[list[dict[str, Any]]], None],
    cudo_machine_types: list[dict[str, Any]],
) -> None:
    # A W2 venue (CUDO) must flow through the registry as soon as its key is present,
    # with no other layer changing (the venues without a key stay skipped).
    monkeypatch.setenv("CUDO_API_KEY", "k")
    patch_cudo_network(cudo_machine_types)

    snaps = fetch_all(now)

    assert {s.source for s in snaps} == {"cudo"}
    assert len(snaps) == 2  # 2 valid GPU machine types
