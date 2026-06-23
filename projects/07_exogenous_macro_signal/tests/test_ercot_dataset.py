"""Test du builder de dataset L0 : alignement point-in-time (anti-look-ahead)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from core.storage.energy_store import EnergyColdStore
from ercot_dataset import build_calibration_dataset


def _write(store: EnergyColdStore, series: str, publish: list, interval: list, value: list) -> None:
    store.write(
        pd.DataFrame(
            {
                "source": "ercot",
                "series": series,
                "publish_time": publish,
                "interval_start": interval,
                "value": value,
            }
        )
    )


def test_build_dataset_is_point_in_time(tmp_path: Path) -> None:
    store = EnergyColdStore(tmp_path)
    pre = pd.Timestamp("2022-07-01T18:00:00Z")  # < cutoff (as_of = 07-01 23:00 UTC)
    post = pd.Timestamp("2022-07-02T12:00:00Z")  # > cutoff → à IGNORER
    t06 = pd.Timestamp("2022-07-02T06:00:00Z")
    t05 = pd.Timestamp("2022-07-02T05:00:00Z")

    # RTM horaire sur le jour J (spike à 06:00) ; publish=interval pour le réalisé.
    rtm_idx = pd.date_range("2022-07-02T00:00", periods=24, freq="1h", tz="UTC")
    rtm_vals = [50.0] * 24
    rtm_vals[6] = 3000.0
    _write(store, "rtm_spp", list(rtm_idx), list(rtm_idx), rtm_vals)

    # Capacité : version pré-cutoff (70000) ET révision post-cutoff (60000) pour 06:00.
    _write(store, "available_capacity", [pre, post], [t06, t06], [70000.0, 60000.0])
    _write(store, "load_forecast", [pre], [t06], [45000.0])
    # Net-load pré-cutoff sur 05:00 et 06:00 (pour le gradient).
    _write(store, "net_load_forecast", [pre, pre], [t05, t06], [38000.0, 42000.0])

    x, y, index = build_calibration_dataset(store, label="abs", threshold_usd_mwh=1500.0)

    pos = list(index).index(t06)
    # Marge = 70000 - 45000 (pré-cutoff) ; la révision post-cutoff 60000 est ignorée.
    assert x[pos, 0] == 25000.0
    # Gradient net-load = 42000 - 38000.
    assert x[pos, 1] == 4000.0
    assert y[pos] == 1.0  # spike (3000 > 1500)
