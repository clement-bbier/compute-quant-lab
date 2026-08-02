"""Tests for the ENTSO-E backfill (long extraction + write idempotence), no network."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from core.storage.energy_store import EnergyColdStore
from infra.collectors.entsoe_backfill import backfill, extract_long


class _FakeClient:
    """Fake ENTSO-E client: returns a fixed 2-point day-ahead series per zone."""

    def query_day_ahead_prices(
        self, country_code: str, start: pd.Timestamp, end: pd.Timestamp
    ) -> pd.Series:
        idx = pd.date_range("2024-06-15T00:00", periods=2, freq="1h", tz="Europe/Paris")
        base = 40.0 if country_code == "FR" else 35.0
        return pd.Series([base, base + 5.0], index=idx, name=country_code)


def test_extract_long_both_zones_tz_preserved() -> None:
    df = extract_long(_FakeClient(), pd.Timestamp("2024-06-15"), pd.Timestamp("2024-06-16"))
    assert set(df["source"]) == {"entsoe_fr", "entsoe_de"}
    assert set(df["series"]) == {"day_ahead_price"}
    assert str(df["publish_time"].dt.tz) == "UTC"
    assert str(df["interval_start"].dt.tz) == "UTC"
    assert len(df) == 4  # 2 zones * 2 points


def test_extract_long_publish_time_is_day_ahead_of_interval() -> None:
    df = extract_long(_FakeClient(), pd.Timestamp("2024-06-15"), pd.Timestamp("2024-06-16"))
    fr = df[df["source"] == "entsoe_fr"].reset_index(drop=True)
    # Interval start 2024-06-15T00:00 Europe/Paris -> publish D-1 (06-14) 12:45 Europe/Paris.
    expected_publish = pd.Timestamp("2024-06-14T12:45", tz="Europe/Paris").tz_convert("UTC")
    assert fr.loc[0, "publish_time"] == expected_publish
    assert fr.loc[0, "publish_time"] < fr.loc[0, "interval_start"]


def test_backfill_writes_then_idempotent(tmp_path: Path) -> None:
    store = EnergyColdStore(tmp_path)
    client = _FakeClient()
    rows1, calls1 = backfill(client, store, "2024-06-15", "2024-06-16", chunk_days=1)
    assert rows1 == 4  # 2 zones * 2 points
    assert calls1 == 2  # 1 chunk * 2 zones
    rows2, calls2 = backfill(client, store, "2024-06-15", "2024-06-16", chunk_days=1)
    assert rows2 == 0  # re-run = no-op (idempotent)
    assert calls2 == 2  # calls are still made; only the write is a no-op
    assert set(store.read()["source"]) == {"entsoe_fr", "entsoe_de"}


class NoMatchingDataError(Exception):
    """Stand-in for ``entsoe.exceptions.NoMatchingDataError`` (matched by class name only)."""


class _GapClient:
    """Fake client where DE has a genuine reporting gap (persists across retries)."""

    def query_day_ahead_prices(
        self, country_code: str, start: pd.Timestamp, end: pd.Timestamp
    ) -> pd.Series:
        if country_code == "DE_LU":
            raise NoMatchingDataError
        idx = pd.date_range("2024-06-15T00:00", periods=2, freq="1h", tz="Europe/Paris")
        return pd.Series([40.0, 45.0], index=idx, name=country_code)


def test_extract_long_skips_zone_with_confirmed_gap() -> None:
    df = extract_long(_GapClient(), pd.Timestamp("2024-06-15"), pd.Timestamp("2024-06-16"))
    assert set(df["source"]) == {"entsoe_fr"}  # DE skipped, FR retained
    assert len(df) == 2
