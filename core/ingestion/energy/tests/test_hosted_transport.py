"""Tests of the injectable ERCOT transport (P17 -- hosted GridStatus.io egress).

Offline: MOCKED hosted client + fixtures of the *presumed* hosted schema. The live test
(``test_fetch_live.py``) validates the real schema with a real key.
"""

from __future__ import annotations

import os

import pandas as pd
import pytest

from core.ingestion.energy.ercot import ErcotMarket
from core.ingestion.energy.ercot_transport import (
    GridstatusDirectTransport,
    GridstatusIoTransport,
)


class _FakeClient:
    """Fake GridStatus.io client: returns frozen frames, records the calls."""

    def __init__(self, frames: dict[str, pd.DataFrame]) -> None:
        self._frames = frames
        self.calls: list[tuple[str, dict]] = []

    def get_dataset(self, dataset: str, **kwargs: object) -> pd.DataFrame:
        self.calls.append((dataset, kwargs))
        return self._frames[dataset]


def _hosted_rtm_frame() -> pd.DataFrame:
    # Presumed hosted schema (snake_case + *_utc). To be confirmed by the live test.
    return pd.DataFrame(
        {
            "interval_start_utc": ["2024-01-15T06:00:00Z", "2024-01-15T06:15:00Z"],
            "interval_end_utc": ["2024-01-15T06:15:00Z", "2024-01-15T06:30:00Z"],
            "location": ["HB_BUSAVG", "HB_BUSAVG"],
            "location_type": ["Trading Hub", "Trading Hub"],
            "market": ["REAL_TIME_15_MIN", "REAL_TIME_15_MIN"],
            "spp": [25.0, 28.0],
        }
    )


def _hosted_forecast_frame() -> pd.DataFrame:
    # REAL schema confirmed live: 4 columns, system-wide forecast (no model dimension).
    return pd.DataFrame(
        {
            "interval_start_utc": ["2024-01-15T06:00:00Z", "2024-01-15T07:00:00Z"],
            "interval_end_utc": ["2024-01-15T07:00:00Z", "2024-01-15T08:00:00Z"],
            "publish_time_utc": ["2024-01-14T23:48:00Z", "2024-01-14T23:48:00Z"],
            "load_forecast": [45000.0, 46000.0],
        }
    )


def test_hosted_transport_maps_rtm_to_canonical_and_parses() -> None:
    client = _FakeClient({"ercot_spp_real_time_15_min": _hosted_rtm_frame()})
    market = ErcotMarket(transport=GridstatusIoTransport(client=client))
    s = market.rtm_price(pd.Timestamp("2024-01-15", tz="UTC"), pd.Timestamp("2024-01-16", tz="UTC"))
    assert s.name == "rtm_price_usd_mwh"
    assert list(s.to_numpy()) == [25.0, 28.0]
    assert str(s.index.tz) == "UTC"
    assert client.calls[0][0] == "ercot_spp_real_time_15_min"  # correct dataset


def test_hosted_transport_maps_forecast_to_canonical() -> None:
    client = _FakeClient({"ercot_load_forecast": _hosted_forecast_frame()})
    market = ErcotMarket(transport=GridstatusIoTransport(client=client))
    df = market.reserve_forecast(
        pd.Timestamp("2024-01-14", tz="UTC"), pd.Timestamp("2024-01-16", tz="UTC")
    )
    for col in ("publish_time", "interval_start", "forecast_load_mw", "reserve_margin_mw"):
        assert col in df.columns
    assert str(df["publish_time"].dt.tz) == "UTC"
    # point-in-time: the forecast is published before the target interval
    assert (df["publish_time"] < df["interval_start"]).all()
    assert list(df["forecast_load_mw"]) == [45000.0, 46000.0]
    # capacity not fabricated -> reserve margin NaN (point 2: no more 70 GW placeholder)
    assert df["reserve_margin_mw"].isna().all()


def test_transport_selection_hosted_when_key_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GRIDSTATUS_API_KEY", "dummy-key")
    assert isinstance(ErcotMarket()._transport(), GridstatusIoTransport)


def test_transport_selection_direct_when_key_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GRIDSTATUS_API_KEY", raising=False)
    assert isinstance(ErcotMarket()._transport(), GridstatusDirectTransport)


def test_injected_transport_takes_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GRIDSTATUS_API_KEY", "dummy-key")
    direct = GridstatusDirectTransport()
    assert ErcotMarket(transport=direct)._transport() is direct


# --- LIVE test (network + real key): validates the real hosted schema ----------
# To be run by the user: `GRIDSTATUS_API_KEY=... uv run pytest -m live`.
# THIS is the test confirming that the mappers (_hosted_*_to_canonical) match the real
# GridStatus.io schema. If it fails on a column, the adjustment is localised.


@pytest.mark.live
def test_hosted_live_rtm_real_schema() -> None:
    key = os.environ.get("GRIDSTATUS_API_KEY")
    if not key:
        pytest.skip("GRIDSTATUS_API_KEY is missing -- export the key for the live test")
    market = ErcotMarket(transport=GridstatusIoTransport(limit=50))
    end = pd.Timestamp.now(tz="UTC").normalize()
    start = end - pd.Timedelta(days=2)
    s = market.rtm_price(start, end)
    assert len(s) > 0
    assert str(s.index.tz) == "UTC"
    assert s.name == "rtm_price_usd_mwh"


@pytest.mark.live
def test_hosted_live_forecast_real_schema() -> None:
    """Validate the real forecast path against the hosted schema confirmed live.

    `_hosted_forecast_to_canonical` maps `*_utc` + `load_forecast` (system-wide forecast, no
    model dimension) from the ercot_load_forecast dataset.
    """
    key = os.environ.get("GRIDSTATUS_API_KEY")
    if not key:
        pytest.skip("GRIDSTATUS_API_KEY is missing -- export the key for the live test")
    market = ErcotMarket(transport=GridstatusIoTransport(limit=500))
    end = pd.Timestamp.now(tz="UTC").normalize()
    start = end - pd.Timedelta(days=1)
    df = market.reserve_forecast(start, end)
    assert len(df) > 0
    assert {"publish_time", "interval_start", "forecast_load_mw"} <= set(df.columns)
    assert str(df["publish_time"].dt.tz) == "UTC"
    assert (df["forecast_load_mw"] > 0).all()
    assert not df.duplicated(["publish_time", "interval_start"]).any()


def test_reserve_forecast_as_of_joins_capacity_no_lookahead() -> None:
    """Point-in-time load-STSA capacity join: nothing published AFTER as_of enters.

    Central anti-look-ahead test (P20): load and capacity each have one version published
    BEFORE as_of and one AFTER; only the earlier versions must count.
    """
    as_of = pd.Timestamp("2024-01-15T00:00:00Z")
    load = pd.DataFrame(
        {
            "interval_start_utc": ["2024-01-15T06:00:00Z", "2024-01-15T06:00:00Z"],
            "interval_end_utc": ["2024-01-15T07:00:00Z", "2024-01-15T07:00:00Z"],
            "publish_time_utc": ["2024-01-14T18:00:00Z", "2024-01-15T06:00:00Z"],
            "load_forecast": [45000.0, 50000.0],
        }
    )
    cap = pd.DataFrame(
        {
            "interval_start_utc": ["2024-01-15T06:00:00Z", "2024-01-15T06:00:00Z"],
            "interval_end_utc": ["2024-01-15T07:00:00Z", "2024-01-15T07:00:00Z"],
            "publish_time_utc": ["2024-01-14T20:00:00Z", "2024-01-15T12:00:00Z"],
            "available_capacity_generation": [70000.0, 60000.0],
        }
    )
    client = _FakeClient({"ercot_load_forecast": load, "ercot_short_term_system_adequacy": cap})
    market = ErcotMarket(transport=GridstatusIoTransport(client=client))
    df = market.reserve_forecast_as_of(as_of)
    assert len(df) == 1
    r = df.iloc[0]
    assert r["forecast_load_mw"] == 45000.0  # published before as_of (not the later 50000)
    assert r["forecast_capacity_mw"] == 70000.0  # published before as_of (not the later 60000)
    assert r["reserve_margin_mw"] == 25000.0  # 70000 - 45000


@pytest.mark.live
def test_hosted_live_reserve_margin_real() -> None:
    """Real reserve margin (load joined with STSA capacity), point-in-time, on real data."""
    key = os.environ.get("GRIDSTATUS_API_KEY")
    if not key:
        pytest.skip("GRIDSTATUS_API_KEY is missing -- export the key for the live test")
    market = ErcotMarket(transport=GridstatusIoTransport(limit=2000))
    as_of = pd.Timestamp.now(tz="UTC").floor("h")
    df = market.reserve_forecast_as_of(as_of)
    assert len(df) > 0
    expected = {"forecast_load_mw", "forecast_capacity_mw", "reserve_margin_mw"}
    assert expected <= set(df.columns)
    assert (df["publish_time"] <= as_of).all()  # point-in-time
    assert df["forecast_capacity_mw"].notna().any()  # real capacity joined


def test_net_load_gradient_as_of_point_in_time() -> None:
    """Predictor 2: point-in-time net-load gradient (nothing after as_of) + ramp = diff."""
    as_of = pd.Timestamp("2024-01-15T00:00:00Z")
    nl = pd.DataFrame(
        {
            "interval_start_utc": [
                "2024-01-15T18:00:00Z",
                "2024-01-15T19:00:00Z",
                "2024-01-15T20:00:00Z",
                "2024-01-15T18:00:00Z",  # revision published AFTER as_of -> to be ignored
            ],
            "interval_end_utc": [
                "2024-01-15T19:00:00Z",
                "2024-01-15T20:00:00Z",
                "2024-01-15T21:00:00Z",
                "2024-01-15T19:00:00Z",
            ],
            "publish_time_utc": [
                "2024-01-14T18:00:00Z",
                "2024-01-14T18:00:00Z",
                "2024-01-14T18:00:00Z",
                "2024-01-15T12:00:00Z",  # > as_of
            ],
            "net_load_forecast": [40000.0, 45000.0, 52000.0, 99999.0],
        }
    )
    client = _FakeClient({"ercot_net_load_forecast": nl})
    market = ErcotMarket(transport=GridstatusIoTransport(client=client))
    df = market.net_load_gradient_as_of(as_of)
    assert len(df) == 3  # the revision published after as_of is discarded
    assert list(df["net_load_mw"]) == [40000.0, 45000.0, 52000.0]
    assert pd.isna(df["net_load_gradient_mw"].iloc[0])  # 1st interval: no ramp
    assert df["net_load_gradient_mw"].iloc[1] == 5000.0
    assert df["net_load_gradient_mw"].iloc[2] == 7000.0  # accelerating ramp


@pytest.mark.live
def test_hosted_live_net_load_gradient_real() -> None:
    """Predictor 2 on real data: confirms the ercot_net_load_forecast dataset/schema."""
    key = os.environ.get("GRIDSTATUS_API_KEY")
    if not key:
        pytest.skip("GRIDSTATUS_API_KEY is missing -- export the key for the live test")
    market = ErcotMarket(transport=GridstatusIoTransport(limit=2000))
    as_of = pd.Timestamp.now(tz="UTC").floor("h")
    df = market.net_load_gradient_as_of(as_of)
    assert len(df) > 0
    assert {"net_load_mw", "net_load_gradient_mw"} <= set(df.columns)
    assert (df["publish_time"] <= as_of).all()
    assert df["net_load_gradient_mw"].notna().any()
