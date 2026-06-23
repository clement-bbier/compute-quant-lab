"""Tests du cold store énergie (idempotence + intégrité point-in-time)."""

from __future__ import annotations

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
    assert store.write(_frame()) == 0  # ré-écrire le même contenu = no-op
    assert len(store.read()) == 2


def test_read_filters_series(tmp_path: Path) -> None:
    store = EnergyColdStore(tmp_path)
    store.write(_frame())
    out = store.read(series="load_forecast")
    assert set(out["series"]) == {"load_forecast"}
    assert len(out) == 1


def test_rejects_naive_timestamp(tmp_path: Path) -> None:
    bad = _frame()
    bad["interval_start"] = pd.Timestamp("2024-01-15T06:00:00")  # naïf → interdit
    with pytest.raises(ValueError, match="naïf"):
        EnergyColdStore(tmp_path).write(bad)


def test_new_publish_time_appends(tmp_path: Path) -> None:
    # Une révision (publish_time plus récent) du même intervalle est conservée (journal).
    store = EnergyColdStore(tmp_path)
    store.write(_frame())
    revised = _frame().iloc[[0]].copy()
    revised["publish_time"] = pd.Timestamp("2024-01-14T19:00:00Z")
    revised["value"] = 46000.0
    assert store.write(revised) == 1
    assert len(store.read(series="load_forecast")) == 2
