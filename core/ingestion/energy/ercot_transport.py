"""Injectable ERCOT transports -- direct egress (geoblocked) vs hosted (US).

Separates the *fetch* (where the data is taken from) from the *normalisation* (the pure
parsers in ``ercot.py``). Two interchangeable transports behind one protocol:

- :class:`GridstatusDirectTransport` -- ``gridstatus.Ercot()`` hitting ercot.com directly.
  **Geoblocked** (Imperva WAF) from non-US IPs.
- :class:`GridstatusIoTransport` -- hosted **GridStatus.io** API (US servers) through
  ``gridstatusio.GridStatusClient``. Legitimately works around the geoblock. Key via
  ``GRIDSTATUS_API_KEY``.

Each transport brings its frames back to the **canonical gridstatus schema** (columns
``"Interval Start"`` / ``"Location"`` / ``"SPP"`` / ``"Publish Time"`` / ``"System
Total"``) that the ``ercot.py`` parsers already consume -- zero parsing duplication.

Hosted schema (snake_case + ``_utc`` suffixes) -- **confirmed against the live API** by the
four ``test_hosted_live_*`` tests in ``tests/test_hosted_transport.py``: every dataset below
and both hosted-only columns map cleanly through the mappers here. Free plan quota: 500k
rows/month -> always pass ``limit`` on large pulls.
"""

from __future__ import annotations

import os
from typing import Protocol

import pandas as pd

from core.utils.logging import get_logger
from core.utils.net import call_with_retry

logger = get_logger(__name__)

#: Dataset IDs of the hosted GridStatus.io API -- confirmed against the live API.
RTM_DATASET = "ercot_spp_real_time_15_min"
FORECAST_DATASET = "ercot_load_forecast"
ADEQUACY_DATASET = "ercot_short_term_system_adequacy"
NET_LOAD_DATASET = "ercot_net_load_forecast"

#: Row cap applied when the caller does not pass an explicit ``limit`` (free plan quota:
#: 500k rows/month -- an uncapped pull on a wide date range could exhaust it in one call).
#: Chosen well under the monthly quota so a handful of such calls still leaves headroom;
#: callers needing more (backfills) pass ``limit`` explicitly.
DEFAULT_GRIDSTATUS_LIMIT: int = 10_000

#: Hosted capacity column kept for the L0 reserve margin -- confirmed against the live API.
_HOSTED_CAPACITY_COL = "available_capacity_generation"
#: Hosted net-load column (absent from the OSS lib -> hosted only) -- confirmed against
#: the live API.
_HOSTED_NETLOAD_COL = "net_load_forecast"


class ErcotTransport(Protocol):
    """ERCOT fetch abstraction -> frames in the canonical gridstatus schema."""

    def fetch_rtm_spp(self, start: pd.Timestamp, end: pd.Timestamp, location: str) -> pd.DataFrame:
        """Raw RTM SPP frame (canonical ``Interval Start``/``Location``/``SPP`` columns)."""
        ...

    def fetch_load_forecast(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        """Raw load forecast frame (canonical ``Publish Time`` and related columns)."""
        ...

    def fetch_system_adequacy(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        """Raw STSA frame (forecast capacity, ``Available Capacity Generation`` column)."""
        ...

    def fetch_net_load_forecast(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        """Raw net-load forecast frame (canonical ``Net Load`` column)."""
        ...


# ---------------------------------------------------------------------------
# Direct transport (gridstatus.Ercot -- geoblocked outside the US)
# ---------------------------------------------------------------------------


class GridstatusDirectTransport:
    """Hits ercot.com directly through ``gridstatus``. Geoblocked (WAF) outside the US."""

    def __init__(self) -> None:
        self._iso: object | None = None  # lazy import/init

    def _get_iso(self) -> object:
        if self._iso is None:
            import gridstatus  # noqa: PLC0415

            self._iso = gridstatus.Ercot()
        return self._iso

    def fetch_rtm_spp(self, start: pd.Timestamp, end: pd.Timestamp, location: str) -> pd.DataFrame:
        import gridstatus  # noqa: PLC0415

        return self._get_iso().get_spp(  # type: ignore[attr-defined,no-any-return]
            date=start,
            end=end,
            market=gridstatus.Markets.REAL_TIME_15_MIN,
            locations=[location],
        )

    def fetch_load_forecast(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        return self._get_iso().get_load_forecast(  # type: ignore[attr-defined,no-any-return]
            date=start, end=end
        )

    def fetch_system_adequacy(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        return self._get_iso().get_short_term_system_adequacy(  # type: ignore[attr-defined,no-any-return]
            date=start, end=end
        )

    def fetch_net_load_forecast(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        # The OSS lib exposes no net-load forecast (real-time only) -> hosted transport only.
        raise NotImplementedError(
            "Net-load forecast is unavailable through direct gridstatus; use the hosted transport."
        )


# ---------------------------------------------------------------------------
# Hosted transport (GridStatus.io -- works around the geoblock)
# ---------------------------------------------------------------------------


class GridstatusIoTransport:
    """Hosted GridStatus.io API (US). Key via ``GRIDSTATUS_API_KEY`` or injected.

    Parameters
    ----------
    api_key
        API key; otherwise read from ``GRIDSTATUS_API_KEY`` on the first call.
    client
        Already-built client (test injection). If provided, ``api_key`` is ignored.
    limit
        Row cap per request (free quota = 500k/month). ``None`` (default) resolves to
        :data:`DEFAULT_GRIDSTATUS_LIMIT` -- omitting ``limit`` never issues an uncapped
        pull; pass a larger ``limit`` explicitly for a backfill that needs more rows.
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        client: object | None = None,
        limit: int | None = None,
    ) -> None:
        self._api_key = api_key
        self._client = client
        if limit is None:
            logger.info(
                "GridStatus.io: no limit specified, capping at default %d rows/request "
                "(free-tier quota protection)",
                DEFAULT_GRIDSTATUS_LIMIT,
            )
        self._limit = limit if limit is not None else DEFAULT_GRIDSTATUS_LIMIT

    def _get_client(self) -> object:
        if self._client is None:
            from gridstatusio import GridStatusClient  # noqa: PLC0415

            key = self._api_key or os.environ.get("GRIDSTATUS_API_KEY")
            if not key:
                raise RuntimeError("GRIDSTATUS_API_KEY must be set: hosted transport unavailable")
            self._client = GridStatusClient(api_key=key)
        return self._client

    def _get_dataset(self, dataset: str, **kwargs: object) -> pd.DataFrame:
        """Retry-wrapped ``get_dataset`` call, shared by every ``fetch_*`` method.

        Retries on 5xx/timeout/connection error only (never on a 4xx): a malformed
        query or bad key will fail identically on a second try and only spends the
        free-tier quota for nothing.
        """
        client = self._get_client()
        return call_with_retry(
            lambda: client.get_dataset(dataset, **kwargs),  # type: ignore[attr-defined]
            venue=f"gridstatus:{dataset}",
        )

    def fetch_rtm_spp(self, start: pd.Timestamp, end: pd.Timestamp, location: str) -> pd.DataFrame:
        raw = self._get_dataset(
            RTM_DATASET,
            start=_date_str(start),
            end=_date_str(end),
            filter_column="location",
            filter_value=location,
            limit=self._limit,
        )
        return _hosted_rtm_to_canonical(raw)

    def fetch_load_forecast(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        raw = self._get_dataset(
            FORECAST_DATASET,
            start=_date_str(start),
            end=_date_str(end),
            limit=self._limit,
        )
        return _hosted_forecast_to_canonical(raw)

    def fetch_system_adequacy(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        raw = self._get_dataset(
            ADEQUACY_DATASET,
            start=_date_str(start),
            end=_date_str(end),
            limit=self._limit,
        )
        return _hosted_adequacy_to_canonical(raw)

    def fetch_net_load_forecast(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        raw = self._get_dataset(
            NET_LOAD_DATASET,
            start=_date_str(start),
            end=_date_str(end),
            limit=self._limit,
        )
        return _hosted_net_load_to_canonical(raw)


# ---------------------------------------------------------------------------
# Hosted schema -> canonical gridstatus schema mappers (live confirmation point)
# ---------------------------------------------------------------------------


def _date_str(ts: pd.Timestamp) -> str:
    """Query bound in ISO date format (the hosted API accepts 'YYYY-MM-DD')."""
    return pd.Timestamp(ts).strftime("%Y-%m-%d")


def _hosted_rtm_to_canonical(df: pd.DataFrame) -> pd.DataFrame:
    """Rename the hosted SPP schema to the canonical gridstatus one (UTC tz-aware times)."""
    return pd.DataFrame(
        {
            "Interval Start": pd.to_datetime(df["interval_start_utc"], utc=True),
            "Interval End": pd.to_datetime(df["interval_end_utc"], utc=True),
            "Location": df["location"].to_numpy(),
            "SPP": df["spp"].astype(float).to_numpy(),
        }
    )


def _hosted_forecast_to_canonical(df: pd.DataFrame) -> pd.DataFrame:
    """Rename the hosted ``ercot_load_forecast`` schema to the canonical gridstatus one.

    REAL schema confirmed live (2026-06): columns ``interval_start_utc`` /
    ``interval_end_utc`` / ``publish_time_utc`` / ``load_forecast`` -- a **system-wide** load
    forecast, one single set per interval (no model dimension).
    """
    return pd.DataFrame(
        {
            "Publish Time": pd.to_datetime(df["publish_time_utc"], utc=True),
            "Interval Start": pd.to_datetime(df["interval_start_utc"], utc=True),
            "Interval End": pd.to_datetime(df["interval_end_utc"], utc=True),
            "System Total": df["load_forecast"].astype(float).to_numpy(),
        }
    )


def _hosted_adequacy_to_canonical(df: pd.DataFrame) -> pd.DataFrame:
    """Rename the hosted ``ercot_short_term_system_adequacy`` schema to the canonical one.

    STSA is a **capacity** report (NOT a demand one). We keep
    ``available_capacity_generation`` (forecast available generation capacity) as the
    capacity of the L0 reserve margin. Hosted name confirmed against the live API.
    """
    return pd.DataFrame(
        {
            "Publish Time": pd.to_datetime(df["publish_time_utc"], utc=True),
            "Interval Start": pd.to_datetime(df["interval_start_utc"], utc=True),
            "Interval End": pd.to_datetime(df["interval_end_utc"], utc=True),
            "Available Capacity Generation": df[_HOSTED_CAPACITY_COL].astype(float).to_numpy(),
        }
    )


def _hosted_net_load_to_canonical(df: pd.DataFrame) -> pd.DataFrame:
    """Rename the hosted ``ercot_net_load_forecast`` schema to the canonical one.

    Net-load = load - renewables (the sunset ramp is the scarcity driver). Hosted column
    ``net_load_forecast`` confirmed against the live API.
    """
    return pd.DataFrame(
        {
            "Publish Time": pd.to_datetime(df["publish_time_utc"], utc=True),
            "Interval Start": pd.to_datetime(df["interval_start_utc"], utc=True),
            "Interval End": pd.to_datetime(df["interval_end_utc"], utc=True),
            "Net Load": df[_HOSTED_NETLOAD_COL].astype(float).to_numpy(),
        }
    )
