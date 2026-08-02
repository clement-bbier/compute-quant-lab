"""Tests of the energy cold store (idempotence + point-in-time integrity)."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import pytest

from core.storage.energy_store import EnergyColdStore


def _frame() -> pd.DataFrame:
    pt = pd.Timestamp("2024-01-14T18:00:00Z")
    it = pd.Timestamp("2024-01-15T06:00:00Z")
    return pd.DataFrame(
        {
            "source": ["ercot", "ercot"],
            "series": ["load_forecast", "net_load_forecast"],
            "publish_time": [pt, pt],
            "interval_start": [it, it],
            "value": [45000.0, 38000.0],
        }
    )


def test_write_then_read_roundtrip(tmp_path: Path) -> None:
    store = EnergyColdStore(tmp_path)
    assert store.write(_frame()) == 2
    out = store.read()
    assert len(out) == 2
    assert set(out["series"]) == {"load_forecast", "net_load_forecast"}
    assert str(out["publish_time"].dt.tz) == "UTC"


def test_write_is_idempotent(tmp_path: Path) -> None:
    store = EnergyColdStore(tmp_path)
    store.write(_frame())
    assert store.write(_frame()) == 0  # rewriting the same content = no-op
    assert len(store.read()) == 2


def test_read_filters_series(tmp_path: Path) -> None:
    store = EnergyColdStore(tmp_path)
    store.write(_frame())
    out = store.read(series="load_forecast")
    assert set(out["series"]) == {"load_forecast"}
    assert len(out) == 1


def test_rejects_naive_timestamp(tmp_path: Path) -> None:
    bad = _frame()
    bad["interval_start"] = pd.Timestamp("2024-01-15T06:00:00")  # naive -> forbidden
    with pytest.raises(ValueError, match="naive"):
        EnergyColdStore(tmp_path).write(bad)


def test_read_empty_lake_logs_warning(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    store = EnergyColdStore(tmp_path)
    with caplog.at_level(logging.WARNING):
        out = store.read()
    assert out.empty
    assert "empty" in caplog.text.lower()


def test_write_logs_new_rows_and_dedup_count(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    store = EnergyColdStore(tmp_path)
    with caplog.at_level(logging.INFO):
        store.write(_frame())
    assert "2 new row" in caplog.text

    caplog.clear()
    with caplog.at_level(logging.INFO):
        store.write(_frame())  # same content -> fully deduplicated
    assert "0 new row" in caplog.text
    assert "2 already present" in caplog.text


def test_new_publish_time_appends(tmp_path: Path) -> None:
    # A revision (more recent publish_time) of the same interval is kept (journal).
    store = EnergyColdStore(tmp_path)
    store.write(_frame())
    revised = _frame().iloc[[0]].copy()
    revised["publish_time"] = pd.Timestamp("2024-01-14T19:00:00Z")
    revised["value"] = 46000.0
    assert store.write(revised) == 1
    assert len(store.read(series="load_forecast")) == 2
