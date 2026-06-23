"""Tests du backfill ERCOT (extraction long + idempotence d'écriture)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from core.storage.energy_store import EnergyColdStore
from infra.collectors.ercot_backfill import backfill, extract_long


class _FakeTransport:
    """Transport ERCOT factice : renvoie des frames canoniques figés."""

    def _idx(self) -> pd.DatetimeIndex:
        return pd.date_range("2024-06-15T18:00", periods=2, freq="1h", tz="UTC")

    def fetch_rtm_spp(self, start: pd.Timestamp, end: pd.Timestamp, location: str) -> pd.DataFrame:
        idx = self._idx()
        return pd.DataFrame(
            {
                "Interval Start": idx,
                "Interval End": idx,
                "Location": location,
                "SPP": [50.0, 2000.0],
            }
        )

    def _forecast(self, value_col: str, values: list[float]) -> pd.DataFrame:
        idx = self._idx()
        return pd.DataFrame(
            {
                "Publish Time": pd.Timestamp("2024-06-14T18:00:00Z"),
                "Interval Start": idx,
                "Interval End": idx,
                value_col: values,
            }
        )

    def fetch_load_forecast(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        return self._forecast("System Total", [45000.0, 46000.0])

    def fetch_system_adequacy(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        return self._forecast("Available Capacity Generation", [70000.0, 71000.0])

    def fetch_net_load_forecast(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        return self._forecast("Net Load", [38000.0, 42000.0])


_SERIES = {"rtm_spp", "load_forecast", "available_capacity", "net_load_forecast"}


def test_extract_long_all_series_tz_preserved() -> None:
    df = extract_long(_FakeTransport(), pd.Timestamp("2024-06-15"), pd.Timestamp("2024-06-16"))
    assert set(df["series"]) == _SERIES
    assert str(df["publish_time"].dt.tz) == "UTC"
    assert str(df["interval_start"].dt.tz) == "UTC"


def test_backfill_writes_then_idempotent(tmp_path: Path) -> None:
    store = EnergyColdStore(tmp_path)
    transport = _FakeTransport()
    n1 = backfill(transport, store, "2024-06-15", "2024-06-16", chunk_days=1)
    assert n1 == 8  # 2 RTM + 2 load + 2 capacité + 2 net-load
    n2 = backfill(transport, store, "2024-06-15", "2024-06-16", chunk_days=1)
    assert n2 == 0  # ré-exécution = no-op (idempotent)
    assert set(store.read()["series"]) == _SERIES
