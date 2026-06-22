"""Tests TDD de la logique pure du serveur MCP gpu-price."""

from __future__ import annotations

import pytest

from conftest import T0, T1  # fixture module (sys.path injecté par conftest)
from service import (
    latest_price,
    list_gpu_models,
    price_history,
    summary_stats,
)


def test_list_gpu_models_sorted(store):
    assert list_gpu_models(store) == ["A100", "B200", "H100"]


def test_list_gpu_models_point_in_time(store):
    # B200 n'existe qu'à T1 → exclu si as_of = T0 (anti look-ahead)
    assert list_gpu_models(store, as_of=T0.isoformat()) == ["A100", "H100"]


def test_naive_as_of_rejected(store):
    with pytest.raises(ValueError, match="naïf"):
        list_gpu_models(store, as_of="2026-06-01T12:00:00")


def test_invalid_iso_as_of_rejected(store):
    with pytest.raises(ValueError, match="ISO 8601 invalide"):
        list_gpu_models(store, as_of="pas-une-date")


def test_empty_store_graceful(tmp_path):
    from core.storage import ParquetPriceStore

    empty = ParquetPriceStore(tmp_path / "empty")
    assert list_gpu_models(empty) == []


def test_latest_price_freshest_per_source_cheapest(store):
    res = latest_price(store, "H100")
    assert res["found"] is True
    assert res["provenance"] == "real"
    by = {d["source"]: d["price_usd_per_hour"] for d in res["by_source"]}
    # vastai : instant le plus récent = T1, offre la moins chère = 1.80 ; runpod T1 = 2.10
    assert by == {"vastai": 1.80, "runpod": 2.10}
    assert res["summary"] == {"min": 1.80, "median": 1.95, "max": 2.10, "n_sources": 2}


def test_latest_price_point_in_time(store):
    res = latest_price(store, "H100", as_of=T0.isoformat())
    by = {d["source"]: d["price_usd_per_hour"] for d in res["by_source"]}
    # à T0 les relevés T1 sont exclus → anti look-ahead
    assert by == {"vastai": 2.00, "runpod": 2.20}


def test_latest_price_unknown_model(store):
    res = latest_price(store, "RTX9999")
    assert res["found"] is False
    assert "RTX9999" in res["message"]
    assert "H100" in res["available_models"]


def test_price_history_ordered_and_source_filter(store):
    res = price_history(store, "H100", source="vastai")
    assert res["n"] == 3  # vastai H100 : T0(2.00), T1(1.80), T1(1.90)
    times = [o["snapshotted_at"] for o in res["observations"]]
    assert times == sorted(times)  # ordre croissant
    assert all(o["source"] == "vastai" for o in res["observations"])


def test_price_history_as_of_excludes_future(store):
    res = price_history(store, "H100", source="vastai", as_of=T0.isoformat())
    assert res["n"] == 1
    assert res["observations"][0]["price_usd_per_hour"] == 2.00


def test_price_history_start_bound(store):
    res = price_history(store, "H100", source="vastai", start=T1.isoformat())
    assert res["n"] == 2
    assert {o["price_usd_per_hour"] for o in res["observations"]} == {1.80, 1.90}


def test_summary_stats_overall_and_by_source(store):
    res = summary_stats(store, "H100")
    # prix H100 : 2.00, 2.20, 1.80, 1.90, 2.10  → 5 obs, mean 2.00, median 2.00
    assert res["n"] == 5
    overall = res["overall"]
    assert overall["count"] == 5
    assert overall["min"] == 1.80
    assert overall["max"] == 2.20
    assert overall["median"] == 2.00
    assert round(overall["mean"], 6) == 2.00
    by = {d["source"]: d["count"] for d in res["by_source"]}
    assert by == {"runpod": 2, "vastai": 3}


def test_summary_stats_as_of(store):
    res = summary_stats(store, "H100", as_of=T0.isoformat())
    assert res["n"] == 2  # T0 seulement : 2.00 (vastai), 2.20 (runpod)
    assert res["overall"]["min"] == 2.00
    assert res["overall"]["max"] == 2.20


def test_summary_stats_unknown_model(store):
    res = summary_stats(store, "RTX9999")
    assert res["found"] is False
    assert res["n"] == 0
