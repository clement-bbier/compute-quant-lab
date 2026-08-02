"""ERCOT (Texas) connector via ``gridstatus`` -- public market, no token.

Confirmed API surface (B0 -- 2026-06-23)
-----------------------------------------
- ``gridstatus.Ercot()`` -- main class, ``default_timezone = "US/Central"``.
- ``iso.get_spp(date, end, market=Markets.REAL_TIME_15_MIN, locations=[...])``
    Output columns: ``["Time", "Interval Start", "Interval End",
    "Location", "Location Type", "Market", "SPP"]``
    Timezone: US/Central (CPT/CDT depending on season).
    Granularity: 15 minute intervals.
    ERCOT source: ``SETTLEMENT_POINT_PRICES_AT_RESOURCE_NODES_HUBS_AND_LOAD_ZONES`` report
    (RTID 12301). Data available from roughly D+0 to D-2.
- ``iso.get_rtm_spp(year)``
    Same columns as ``get_spp``. Historical depth: since 2011 (yearly).
    Source: ``HISTORICAL_RTM_LOAD_ZONE_AND_HUB_PRICES`` (RTID 13061).
- ``iso.get_load_forecast(date, end, forecast_type=ERCOTSevenDayLoadForecastReport.BY_FORECAST_ZONE)``
    Output columns: ``["Time", "Interval Start", "Interval End", "Publish Time",
    "Coast", "East", "Far West", "North", "North Central", "South Central",
    "Southern", "West", "System Total"]``
    Timezone: US/Central.
    Granularity: hourly. Historical depth: limited (a few weeks).
    Source: ``ERCOT_SEVEN_DAY_LOAD_FORECAST_BY_FORECAST_ZONE`` (RTID 12311).

Publication time of the forecast reports (critical for L0 section 2 point-in-time)
----------------------------------------------------------------------------------
ERCOT publishes the Seven-Day Load Forecast report roughly every hour. The ``Publish Time``
column returned by ``get_load_forecast`` is timestamped at the actual publication (e.g.
17:48, 18:02 CPT), not at the target time. The L0 decision cutoff is ~18:00 CPT D-1: the
17:48 or 18:02 CPT D-1 report must be the last usable one. Our parser preserves
``Publish Time`` and converts it to UTC for the calibration layer.

NETWORK NOTE: the ercot.com API is blocked by the Imperva (Incapsula) WAF from some non-US
networks (code 403). The live smoke test (test_fetch_live.py) is marked ``@live`` and must be
run from a US network or through a suitable proxy.

Standard hub locations for the ERCOT system price
--------------------------------------------------
- ``"HB_BUSAVG"`` : system-wide hub (bus weighted average) -> representative price.
- ``"HB_WEST"``   : West hub (datacenter/mining concentration, L0 section 4 secondary label).
- ``"LZ_HOUSTON"`` / ``"LZ_NORTH"`` / ``"LZ_SOUTH"`` / ``"LZ_WEST"`` : load zones.

Units
-----
- RTM price: $/MWh (gridstatus ``SPP`` column -> ``rtm_price_usd_mwh``).
- Load / capacity: MW.
- All internal timestamps: UTC tz-aware.
"""

from __future__ import annotations

import os

import pandas as pd

from core.ingestion.energy.base import register_market
from core.ingestion.energy.ercot_transport import (
    ErcotTransport,
    GridstatusDirectTransport,
    GridstatusIoTransport,
)
from core.utils.logging import get_logger

logger = get_logger(__name__)

# Default location for the ERCOT system RTM price
_DEFAULT_RTM_LOCATION = "HB_BUSAVG"

# gridstatus column names (constants to avoid duplicated literals)
_COL_INTERVAL_START = "Interval Start"
_COL_INTERVAL_END = "Interval End"
_COL_PUBLISH_TIME = "Publish Time"
_COL_SYSTEM_TOTAL = "System Total"
_COL_AVAIL_CAP_GEN = "Available Capacity Generation"
_COL_NET_LOAD = "Net Load"

# Fetch window around as_of (reserve_forecast_as_of): the hosted API rejects a zero-width
# range. Lookback = catch the latest publications known <= as_of; horizon = catch the future
# target intervals (6-7 day forecasts).
# Point-in-time filtering remains guaranteed by `_latest_known_per_interval`.
_ASOF_FETCH_LOOKBACK = pd.Timedelta(days=2)
_ASOF_FETCH_HORIZON = pd.Timedelta(days=2)


# ---------------------------------------------------------------------------
# Pure parsers (I/O isolated, testable on frozen fixtures)
# ---------------------------------------------------------------------------


def parse_rtm_spp(
    df: pd.DataFrame,
    location: str = _DEFAULT_RTM_LOCATION,
) -> pd.Series:
    """Parse a gridstatus get_spp / get_rtm_spp DataFrame -> pd.Series $/MWh UTC.

    Parameters
    ----------
    df
        Raw DataFrame returned by ``iso.get_spp()`` or ``iso.get_rtm_spp()`` with the
        ``["Interval Start", "Location", "SPP"]`` columns (at minimum).
    location
        ERCOT hub/zone identifier to filter on (e.g. ``"HB_BUSAVG"``).

    Returns
    -------
    pd.Series
        Indexed by ``Interval Start`` (UTC tz-aware), values in $/MWh, sorted
        chronologically, with no injected NaN, named ``"rtm_price_usd_mwh"``.

    Raises
    ------
    ValueError
        If ``location`` does not exist in the DataFrame.
    """
    # Filter on the requested location
    available = df["Location"].unique().tolist() if "Location" in df.columns else []
    if location not in available:
        raise ValueError(f"location ('{location}') must be one of the available: {available}")

    sub = df[df["Location"] == location].copy()

    # Retrieve the time index column
    time_col = _COL_INTERVAL_START if _COL_INTERVAL_START in sub.columns else "Time"

    # Convert to UTC tz-aware
    idx = _to_utc(pd.to_datetime(sub[time_col]))

    series = pd.Series(
        sub["SPP"].values,
        index=idx,
        name="rtm_price_usd_mwh",
        dtype=float,
    )

    # Sort chronologically and drop any duplicates (keeps the last one)
    series = series.sort_index()

    return series


def parse_load_forecast(df: pd.DataFrame) -> pd.DataFrame:
    """Parse a gridstatus get_load_forecast DataFrame -> UTC-normalised DataFrame.

    Normalises the columns to the ``EnergyMarket.reserve_forecast`` contract:
    - ``publish_time``        : report publication time (UTC tz-aware).
    - ``interval_start``      : target start time (UTC tz-aware).
    - ``interval_end``        : target end time (UTC tz-aware).
    - ``forecast_load_mw``    : forecast load (System Total, MW).
    - ``forecast_capacity_mw``: forecast available capacity (MW), **only from a real
      source**. Absent from the load report -> ``NaN`` (never fabricated: a placeholder
      would silently corrupt the L0 reserve margin predictor). Wiring a real capacity
      (Short-Term System Adequacy) is a dedicated task.
    - ``reserve_margin_mw``   : margin = capacity - load (MW), ``NaN`` for as long as the
      real capacity is not wired in.

    L0 section 2 point-in-time: ``publish_time`` is preserved from the gridstatus
    ``Publish Time`` column and converted to UTC. The ``publish_time < interval_start``
    invariant is guaranteed by the nature of the report (a forecast published before the
    target time).

    Parameters
    ----------
    df
        Raw DataFrame returned by ``iso.get_load_forecast()``.

    Returns
    -------
    pd.DataFrame
        Normalised columns, sorted by (``publish_time``, ``interval_start``).
    """
    out = pd.DataFrame()

    # Time columns
    time_col = _COL_INTERVAL_START if _COL_INTERVAL_START in df.columns else "Time"

    out["publish_time"] = _to_utc(pd.to_datetime(df[_COL_PUBLISH_TIME]))
    out["interval_start"] = _to_utc(pd.to_datetime(df[time_col]))
    out["interval_end"] = _to_utc(pd.to_datetime(df[_COL_INTERVAL_END]))

    # Forecast load: "System Total" column (sum over all zones)
    load_col = _COL_SYSTEM_TOTAL if _COL_SYSTEM_TOTAL in df.columns else df.columns[-1]
    out["forecast_load_mw"] = df[load_col].astype(float).values

    # Forecast capacity: ONLY from a real source, never fabricated.
    # Absent -> NaN (visible) rather than a placeholder that would corrupt the L0 predictor.
    if "forecast_capacity_mw" in df.columns:
        out["forecast_capacity_mw"] = df["forecast_capacity_mw"].astype(float).values
    elif "Available Capacity" in df.columns:
        out["forecast_capacity_mw"] = df["Available Capacity"].astype(float).values
    else:
        out["forecast_capacity_mw"] = float("nan")

    # Reserve margin = capacity - load
    out["reserve_margin_mw"] = out["forecast_capacity_mw"] - out["forecast_load_mw"]

    # Point-in-time sort
    out = out.sort_values(["publish_time", "interval_start"]).reset_index(drop=True)

    return out


def parse_system_adequacy(df: pd.DataFrame) -> pd.DataFrame:
    """Parse a canonical STSA DataFrame -> normalised forecast capacity (UTC, point-in-time).

    STSA (Short-Term System Adequacy) is a **capacity** report: no demand. We keep
    ``Available Capacity Generation`` (forecast available generation capacity) as the
    capacity of the L0 reserve margin.

    Returns
    -------
    pd.DataFrame
        Columns ``publish_time`` / ``interval_start`` / ``interval_end`` /
        ``forecast_capacity_mw`` (UTC tz-aware), sorted by (publish_time, interval_start).
    """
    time_col = _COL_INTERVAL_START if _COL_INTERVAL_START in df.columns else "Time"
    out = pd.DataFrame()
    out["publish_time"] = _to_utc(pd.to_datetime(df[_COL_PUBLISH_TIME]))
    out["interval_start"] = _to_utc(pd.to_datetime(df[time_col]))
    out["interval_end"] = _to_utc(pd.to_datetime(df[_COL_INTERVAL_END]))
    out["forecast_capacity_mw"] = df[_COL_AVAIL_CAP_GEN].astype(float).values
    return out.sort_values(["publish_time", "interval_start"]).reset_index(drop=True)


def parse_net_load_forecast(df: pd.DataFrame) -> pd.DataFrame:
    """Parse a canonical net-load DataFrame -> normalised net-load forecast (UTC, point-in-time).

    Net-load = load - renewables. Output columns: ``publish_time`` / ``interval_start`` /
    ``interval_end`` / ``net_load_mw``.
    """
    time_col = _COL_INTERVAL_START if _COL_INTERVAL_START in df.columns else "Time"
    out = pd.DataFrame()
    out["publish_time"] = _to_utc(pd.to_datetime(df[_COL_PUBLISH_TIME]))
    out["interval_start"] = _to_utc(pd.to_datetime(df[time_col]))
    out["interval_end"] = _to_utc(pd.to_datetime(df[_COL_INTERVAL_END]))
    out["net_load_mw"] = df[_COL_NET_LOAD].astype(float).values
    return out.sort_values(["publish_time", "interval_start"]).reset_index(drop=True)


def _latest_known_per_interval(df: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    """Keep, per ``interval_start``, the last version published **at/before** ``as_of``.

    Look-ahead guardrail (L0): first filters ``publish_time <= as_of`` (nothing published
    after the decision cutoff), then takes the most recent publication per interval.
    """
    known = df[df["publish_time"] <= as_of]
    if known.empty:
        return known
    idx = known.groupby("interval_start")["publish_time"].idxmax()
    return known.loc[idx]


# ---------------------------------------------------------------------------
# UTC conversion helper
# ---------------------------------------------------------------------------


def _to_utc(series: pd.Series) -> pd.Series:
    """Convert a pd.Series of timestamps to UTC tz-aware.

    Handles the cases: naive (assumes US/Central), US/Central, UTC.
    """
    if series.dt.tz is None:
        # Naive timestamps from a CSV read without tz -> assume US/Central
        series = series.dt.tz_localize("US/Central", ambiguous="infer", nonexistent="shift_forward")
    return series.dt.tz_convert("UTC")


# ---------------------------------------------------------------------------
# ErcotMarket connector (wraps gridstatus, implements EnergyMarket)
# ---------------------------------------------------------------------------


@register_market("ercot")
class ErcotMarket:
    """ERCOT Texas connector via ``gridstatus.Ercot()``.

    Public market (``required_env = ()``), always listed in the registry.
    Real ERCOT data -- no ``simulated`` flag required (L0 section 2).

    Network notes
    -------------
    The ercot.com API is blocked by the Imperva WAF from some non-US networks. Use the live
    smoke test (``pytest -m live``) from a US network to validate a real call. The unit tests
    (B2) run on frozen fixtures.
    """

    name = "ercot"
    required_env: tuple[str, ...] = ()

    def __init__(self, transport: ErcotTransport | None = None) -> None:
        """``transport`` is injected (tests/override); otherwise resolved lazily."""
        self._injected = transport
        self._resolved: ErcotTransport | None = None

    def _transport(self) -> ErcotTransport:
        """Resolve the transport: injected > hosted (key present) > direct (geoblocked)."""
        if self._injected is not None:
            logger.info("ERCOT transport resolved: injected (%s)", type(self._injected).__name__)
            return self._injected
        resolved = self._resolved
        if resolved is None:
            if os.environ.get("GRIDSTATUS_API_KEY"):
                logger.info("ERCOT transport resolved: hosted (GridStatus.io, key present)")
                resolved = GridstatusIoTransport()
            else:
                logger.info("ERCOT transport resolved: direct (gridstatus.Ercot, no key)")
                resolved = GridstatusDirectTransport()
            self._resolved = resolved
        return resolved

    def rtm_price(
        self,
        start: pd.Timestamp,
        end: pd.Timestamp,
        location: str = _DEFAULT_RTM_LOCATION,
    ) -> pd.Series:
        """ERCOT RTM price over [start, end], for a hub/zone location.

        Parameters
        ----------
        start, end
            Range bounds (UTC tz-aware recommended; converted to US/Central for the
            gridstatus call, returned in UTC).
        location
            ERCOT hub or load zone (default: ``"HB_BUSAVG"``).

        Returns
        -------
        pd.Series
            Indexed by Interval Start (UTC), values in $/MWh, sorted, without NaN.
        """
        df = self._transport().fetch_rtm_spp(start, end, location)
        return parse_rtm_spp(df, location=location)

    def reserve_forecast(
        self,
        start: pd.Timestamp,
        end: pd.Timestamp,
    ) -> pd.DataFrame:
        """Load forecasts published between start and end (publication range).

        L0 section 2 point-in-time: returns every report whose publication date falls in
        [start, end]. The caller then filters on ``publish_time <= cutoff_18h_j1``.

        Parameters
        ----------
        start, end
            Bounds of the publication window (UTC tz-aware).

        Returns
        -------
        pd.DataFrame
            Normalised columns (see ``parse_load_forecast``), UTC tz-aware.
        """
        df = self._transport().fetch_load_forecast(start, end)
        return parse_load_forecast(df)

    def reserve_forecast_as_of(
        self,
        as_of: pd.Timestamp,
    ) -> pd.DataFrame:
        """Forecast reserve margin known at ``as_of`` (strict point-in-time, L0 predictor).

        Cross-dataset join: **load** (``ercot_load_forecast``) joined with **capacity**
        (STSA), each reduced to its last publication ``<= as_of`` per interval.
        Margin = capacity - load. No value published after ``as_of`` enters (the look-ahead
        guardrail lives in :func:`_latest_known_per_interval`).

        Parameters
        ----------
        as_of
            Decision timestamp (UTC tz-aware), e.g. the ~18:00 CPT D-1 cutoff.

        Returns
        -------
        pd.DataFrame
            ``interval_start`` / ``interval_end`` / ``publish_time`` /
            ``forecast_load_mw`` / ``forecast_capacity_mw`` / ``reserve_margin_mw``.
            ``forecast_capacity_mw`` (and hence the margin) is ``NaN`` if no STSA capacity
            has a matching interval.
        """
        transport = self._transport()
        # Non-zero window (the hosted API rejects start == end); point-in-time is guaranteed
        # by the publish_time <= as_of filter in _latest_known_per_interval.
        start = as_of - _ASOF_FETCH_LOOKBACK
        end = as_of + _ASOF_FETCH_HORIZON
        load = _latest_known_per_interval(
            parse_load_forecast(transport.fetch_load_forecast(start, end)), as_of
        )[["interval_start", "interval_end", "publish_time", "forecast_load_mw"]]
        cap = _latest_known_per_interval(
            parse_system_adequacy(transport.fetch_system_adequacy(start, end)), as_of
        )[["interval_start", "forecast_capacity_mw"]]

        out = load.merge(cap, on="interval_start", how="left")
        out["reserve_margin_mw"] = out["forecast_capacity_mw"] - out["forecast_load_mw"]
        return out.sort_values("interval_start").reset_index(drop=True)

    def net_load_gradient_as_of(self, as_of: pd.Timestamp) -> pd.DataFrame:
        """Gradient (ramp) of the net-load forecast known at ``as_of`` -- L0 **predictor 2**.

        Latest net-load forecast ``<= as_of`` per interval, sorted, then the **first
        derivative** (inter-interval ramp). The ramp peak (solar drop-off at sunset + high
        residential demand) is a scarcity driver.
        Point-in-time: nothing published after ``as_of`` (via ``_latest_known_per_interval``);
        the gradient only uses the forecast curve known at ``as_of``.

        Returns
        -------
        pd.DataFrame
            ``interval_start`` / ``publish_time`` / ``net_load_mw`` /
            ``net_load_gradient_mw`` (``NaN`` on the first interval).
        """
        start = as_of - _ASOF_FETCH_LOOKBACK
        end = as_of + _ASOF_FETCH_HORIZON
        nl = parse_net_load_forecast(self._transport().fetch_net_load_forecast(start, end))
        nl = _latest_known_per_interval(nl, as_of).sort_values("interval_start")
        out = nl[["interval_start", "publish_time", "net_load_mw"]].reset_index(drop=True)
        out["net_load_gradient_mw"] = out["net_load_mw"].diff()
        return out
