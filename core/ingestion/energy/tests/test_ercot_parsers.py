"""Tests of the ERCOT parsers on frozen fixtures (B2).

Test the pure logic of the parsers (I/O isolated) without any network call.
The CSV fixtures are real samples captured in B0 and frozen here to guarantee test
reproducibility (determinism required).

Guarantees tested:
- RTM output: pd.Series UTC tz-aware, sorted, in $/MWh, with no injected NaN.
- Reserve forecast: ``publish_time`` column timestamped at the PUBLICATION time (not the
  target) -> guarantees the L0 section 2 point-in-time.
- ``reserve_margin_mw`` = ``forecast_capacity_mw`` - ``forecast_load_mw``.
"""

from __future__ import annotations

import pathlib

import pandas as pd
import pytest

from core.ingestion.energy.ercot import parse_rtm_spp, parse_load_forecast

# ---------------------------------------------------------------------------
# Paths of the frozen fixtures
# ---------------------------------------------------------------------------

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
RTM_FIXTURE = FIXTURES / "ercot_rtm_spp_sample.csv"
FORECAST_FIXTURE = FIXTURES / "ercot_load_forecast_sample.csv"


# ---------------------------------------------------------------------------
# Tests parse_rtm_spp
# ---------------------------------------------------------------------------


class TestParseRtmSpp:
    """Parser of the ERCOT RTM price (Settlement Point Price)."""

    def test_returns_series(self) -> None:
        """The parser returns a pd.Series (not a DataFrame)."""
        df_raw = pd.read_csv(RTM_FIXTURE, parse_dates=["Time", "Interval Start", "Interval End"])
        result = parse_rtm_spp(df_raw, location="HB_BUSAVG")
        assert isinstance(result, pd.Series)

    def test_index_is_utc(self) -> None:
        """The series index is UTC tz-aware."""
        df_raw = pd.read_csv(RTM_FIXTURE, parse_dates=["Time", "Interval Start", "Interval End"])
        result = parse_rtm_spp(df_raw, location="HB_BUSAVG")
        index = pd.DatetimeIndex(result.index)
        assert index.tz is not None
        assert str(index.tz) == "UTC"

    def test_series_name(self) -> None:
        """The series name is rtm_price_usd_mwh."""
        df_raw = pd.read_csv(RTM_FIXTURE, parse_dates=["Time", "Interval Start", "Interval End"])
        result = parse_rtm_spp(df_raw, location="HB_BUSAVG")
        assert result.name == "rtm_price_usd_mwh"

    def test_sorted_chronologically(self) -> None:
        """The series is sorted chronologically (monotonically increasing)."""
        df_raw = pd.read_csv(RTM_FIXTURE, parse_dates=["Time", "Interval Start", "Interval End"])
        result = parse_rtm_spp(df_raw, location="HB_BUSAVG")
        assert result.index.is_monotonic_increasing

    def test_no_nan_injected(self) -> None:
        """No NaN is injected into the series (do not mask gaps)."""
        df_raw = pd.read_csv(RTM_FIXTURE, parse_dates=["Time", "Interval Start", "Interval End"])
        result = parse_rtm_spp(df_raw, location="HB_BUSAVG")
        assert not result.isna().any()

    def test_values_in_usd_per_mwh(self) -> None:
        """The values match the fixture prices ($/MWh, HB_BUSAVG)."""
        df_raw = pd.read_csv(RTM_FIXTURE, parse_dates=["Time", "Interval Start", "Interval End"])
        result = parse_rtm_spp(df_raw, location="HB_BUSAVG")
        # The 4 HB_BUSAVG prices of the fixture
        expected = [35.12, 36.45, 34.87, 37.23]
        assert list(result.values) == pytest.approx(expected, rel=1e-6)

    def test_location_filter(self) -> None:
        """Only the requested location is returned (no hub/zone mixing)."""
        df_raw = pd.read_csv(RTM_FIXTURE, parse_dates=["Time", "Interval Start", "Interval End"])
        hub = parse_rtm_spp(df_raw, location="HB_BUSAVG")
        zone = parse_rtm_spp(df_raw, location="LZ_HOUSTON")
        assert len(hub) == 4
        assert len(zone) == 4
        # The prices must differ
        assert list(hub.values) != pytest.approx(list(zone.values), abs=0.01)

    def test_unknown_location_raises(self) -> None:
        """An unknown location raises ValueError (fail-fast)."""
        df_raw = pd.read_csv(RTM_FIXTURE, parse_dates=["Time", "Interval Start", "Interval End"])
        with pytest.raises(ValueError, match="HB_MISSING"):
            parse_rtm_spp(df_raw, location="HB_MISSING")


# ---------------------------------------------------------------------------
# parse_load_forecast tests (L0 point-in-time)
# ---------------------------------------------------------------------------


class TestParseLoadForecast:
    """Parser of the ERCOT load/reserve forecast.

    The ``publish_time`` column is the key to the L0 section 2 point-in-time: it must be
    timestamped at the report PUBLICATION time, never at the forecast target time.
    """

    def _load(self) -> pd.DataFrame:
        return pd.read_csv(
            FORECAST_FIXTURE,
            parse_dates=["Time", "Interval Start", "Interval End", "Publish Time"],
        )

    def test_returns_dataframe(self) -> None:
        """The parser returns a pd.DataFrame."""
        result = parse_load_forecast(self._load())
        assert isinstance(result, pd.DataFrame)

    def test_required_columns_present(self) -> None:
        """The minimum columns of the EnergyMarket contract are present."""
        result = parse_load_forecast(self._load())
        required = {
            "publish_time",
            "interval_start",
            "interval_end",
            "forecast_load_mw",
            "forecast_capacity_mw",
            "reserve_margin_mw",
        }
        assert required.issubset(set(result.columns))

    def test_publish_time_is_utc(self) -> None:
        """publish_time is UTC tz-aware: L0 section 2 point-in-time guarantee."""
        result = parse_load_forecast(self._load())
        assert result["publish_time"].dt.tz is not None
        assert str(result["publish_time"].dt.tz) == "UTC"

    def test_interval_start_is_utc(self) -> None:
        """interval_start is UTC tz-aware."""
        result = parse_load_forecast(self._load())
        assert result["interval_start"].dt.tz is not None
        assert str(result["interval_start"].dt.tz) == "UTC"

    def test_publish_time_precedes_interval_start(self) -> None:
        """publish_time < interval_start: the report is published BEFORE the target.

        L0 section 6 causal invariant: the forecast is known BEFORE the target time.
        """
        result = parse_load_forecast(self._load())
        assert (result["publish_time"] < result["interval_start"]).all()

    def test_reserve_margin_equals_capacity_minus_load(self) -> None:
        """reserve_margin_mw = forecast_capacity_mw - forecast_load_mw (coherence)."""
        result = parse_load_forecast(self._load())
        expected = result["forecast_capacity_mw"] - result["forecast_load_mw"]
        pd.testing.assert_series_equal(
            result["reserve_margin_mw"],
            expected,
            check_names=False,
            rtol=1e-6,
        )

    def test_sorted_by_publish_then_interval(self) -> None:
        """Sort: (publish_time ASC, interval_start ASC)."""
        result = parse_load_forecast(self._load())
        expected = result.sort_values(["publish_time", "interval_start"])
        pd.testing.assert_frame_equal(
            result.reset_index(drop=True),
            expected.reset_index(drop=True),
        )

    def test_capacity_nan_when_no_real_source(self) -> None:
        """Without a REAL capacity source, forecast_capacity_mw is NaN -- never fabricated.

        The 70 GW placeholder was removed (risk-validator review): fabricating the capacity
        would silently corrupt the L0 reserve margin predictor. A visible NaN beats a fake
        number. The real capacity (Short-Term System Adequacy) will be wired in by a dedicated
        task. The load fixture carries no capacity.
        """
        result = parse_load_forecast(self._load())
        assert result["forecast_capacity_mw"].isna().all()
        assert result["reserve_margin_mw"].isna().all()
