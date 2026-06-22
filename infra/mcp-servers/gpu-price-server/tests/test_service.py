"""Tests TDD de la logique pure du serveur MCP gpu-price."""

from __future__ import annotations

import pytest

from conftest import T0  # fixture module (sys.path injecté par conftest)
from service import (
    list_gpu_models,
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
