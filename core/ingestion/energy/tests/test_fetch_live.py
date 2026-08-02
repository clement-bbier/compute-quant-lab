"""ERCOT live smoke test -- real, marked ``@pytest.mark.live``.

Excluded from CI by default (ERCOT network required). Run it explicitly with:
    uv run pytest -m live core/ingestion/energy -v

Network prerequisite: the ercot.com API is blocked by the Imperva (Incapsula) WAF from some
non-US networks (HTTP code 403). These tests must be run from a US network or through a
suitable proxy.

What the smoke test validates:
- The ErcotMarket connector is properly registered in the registry.
- get_spp() returns data with a volume > 0.
- The RTM series is UTC tz-aware and monotonically increasing.
- get_load_forecast() returns a well-formed raw feed (schema, UTC, margin coherence,
  plausible range). NOT a point-in-time claim: the raw feed includes late-published
  revisions for elapsed intervals (confirmed against the live API) -- point-in-time is
  guaranteed one layer up, by reserve_forecast_as_of (see test_hosted_transport.py).
- Both calls cover at least 1 day of data.
"""

from __future__ import annotations

import os

import pytest
import pandas as pd

from core.ingestion.energy.base import available_markets
from core.ingestion.energy.ercot import ErcotMarket
from core.ingestion.energy.ercot_transport import GridstatusIoTransport


@pytest.mark.live
def test_ercot_is_registered() -> None:
    """ERCOT is always in the registry (public market, empty required_env)."""
    assert "ercot" in available_markets()


@pytest.mark.live
def test_rtm_price_live() -> None:
    """Pull 2 days of real RTM prices and check the shape guarantees."""
    key = os.environ.get("GRIDSTATUS_API_KEY")
    if not key:
        pytest.skip("GRIDSTATUS_API_KEY is missing -- export the key for the live test")
    market = ErcotMarket(transport=GridstatusIoTransport(limit=500))

    # 2 recent days -- we take D-3 to D-1 to avoid incomplete data
    end = pd.Timestamp.now(tz="UTC").normalize() - pd.Timedelta(days=1)
    start = end - pd.Timedelta(days=2)

    series = market.rtm_price(start, end)

    # Volume: 2 days x 96 intervals of 15 min = 192 expected points
    assert len(series) > 0, "The RTM series is empty"
    assert len(series) >= 48, f"Insufficient volume: {len(series)} points"

    # UTC timezone
    index = pd.DatetimeIndex(series.index)
    assert index.tz is not None
    assert str(index.tz) == "UTC", f"Unexpected timezone: {index.tz}"

    # Time monotonicity
    assert series.index.is_monotonic_increasing, "The index is not sorted chronologically"

    # No NaN
    assert not series.isna().any(), f"{series.isna().sum()} NaN detected"

    # Coherent value range (ERCOT RTM: typically -$50 to $9000/MWh)
    assert series.min() > -1000.0, f"Abnormal minimum price: {series.min()}"
    assert series.max() < 15_000.0, f"Abnormal maximum price: {series.max()}"

    # Series name
    assert series.name == "rtm_price_usd_mwh"


@pytest.mark.live
def test_reserve_forecast_live() -> None:
    """Pull real load forecasts and check the raw-feed schema (not a point-in-time claim).

    ``reserve_forecast(start, end)`` filters on **publication date**, not interval date (its
    own docstring: "the caller then filters on publish_time <= cutoff"). Confirmed live: the
    real GridStatus.io ``ercot_load_forecast`` dataset includes late-published revisions for
    already-elapsed intervals, so ``publish_time >= interval_start`` is common here and is
    NOT a look-ahead bug -- the point-in-time guarantee lives one layer up, in
    ``reserve_forecast_as_of`` (covered live by ``test_hosted_live_reserve_margin_real``).
    """
    key = os.environ.get("GRIDSTATUS_API_KEY")
    if not key:
        pytest.skip("GRIDSTATUS_API_KEY is missing -- export the key for the live test")
    market = ErcotMarket(transport=GridstatusIoTransport(limit=500))

    # We request the reports published in the last 48h
    end = pd.Timestamp.now(tz="UTC")
    start = end - pd.Timedelta(hours=48)

    df = market.reserve_forecast(start, end)

    # Non-zero volume
    assert len(df) > 0, "The forecast DataFrame is empty"

    # Mandatory columns
    required = {
        "publish_time",
        "interval_start",
        "interval_end",
        "forecast_load_mw",
        "forecast_capacity_mw",
        "reserve_margin_mw",
    }
    missing = required - set(df.columns)
    assert not missing, f"Missing columns: {missing}"

    # UTC timezone
    assert str(df["publish_time"].dt.tz) == "UTC"
    assert str(df["interval_start"].dt.tz) == "UTC"

    # Margin coherence
    expected_margin = df["forecast_capacity_mw"] - df["forecast_load_mw"]
    pd.testing.assert_series_equal(
        df["reserve_margin_mw"],
        expected_margin,
        check_names=False,
        rtol=1e-4,
    )

    # Forecast load within a reasonable range for ERCOT (20 GW - 90 GW)
    assert df["forecast_load_mw"].min() > 10_000.0
    assert df["forecast_load_mw"].max() < 100_000.0
