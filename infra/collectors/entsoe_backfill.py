"""Historical ENTSO-E backfill: FR/DE day-ahead prices to the energy cold store.

Pulls day-ahead auction prices (EUR/MWh) per zone, in **point-in-time long format**, and
writes them to :class:`EnergyColdStore` (Parquet, versioned as plain git). P02/P05 read this
immutable lake (see the training-cold-store rule), never the live feed, once it is committed.

``entsoe-py`` returns no publication timestamp, so ``publish_time`` is an **approximated
convention** documented in ``core.storage.energy_store``: day-ahead auction results are
published around D-1 ~12:45 Europe/Paris (CET/CEST) -- ``publish_time`` is therefore derived
from ``interval_start`` (D-1, 12:45 local Paris time, converted to UTC), never read from the
API. Realized prices (the day-ahead auction clears once, is not revised) so this is a stable,
if approximate, point-in-time anchor.

Zones are encoded in ``source`` (``"entsoe_fr"`` / ``"entsoe_de"``), ``series`` stays
``"day_ahead_price"` for every zone -- mirrors how the ERCOT backfill puts the market into
``source="ercot"``; here the zone plays that role since each region needs its own filterable
series.

Warning: this is operational and requires ``ENTSOE_API_TOKEN``. ENTSO-E's free tier has no
published hard quota but is rate-limited -- chunk by month and space out large ranges.

Usage: ``uv run python -m infra.collectors.entsoe_backfill --start 2024-01-01 --end 2025-01-01``.
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path
from typing import Protocol

import pandas as pd

from core.storage.energy_store import (
    INTERVAL_START,
    PUBLISH_TIME,
    SERIES,
    SOURCE,
    VALUE,
    EnergyColdStore,
)
from core.utils.logging import get_logger

log = get_logger("entsoe_backfill")

#: ENTSO-E bidding-zone code (as accepted by ``entsoe-py``'s ``query_day_ahead_prices``) ->
#: cold-store source label. Germany's day-ahead bidding zone is DE-LU (post-2018 merger with
#: Luxembourg); the plain ``"DE"`` country code returns no data (confirmed empirically).
_ZONES: dict[str, str] = {"FR": "entsoe_fr", "DE_LU": "entsoe_de"}
_SERIES_NAME = "day_ahead_price"
#: Day-ahead auction publication convention (approximated, see module docstring).
_PUBLISH_HOUR_LOCAL = 12
_PUBLISH_MINUTE_LOCAL = 45
_PUBLISH_TZ = "Europe/Paris"


class DayAheadClient(Protocol):
    """ENTSO-E fetch abstraction -> a single zone's day-ahead price series."""

    def query_day_ahead_prices(
        self, country_code: str, start: pd.Timestamp, end: pd.Timestamp
    ) -> pd.Series:
        """Day-ahead prices (EUR/MWh) for ``country_code`` over ``[start, end]``."""
        ...


def _approximate_publish_time(interval_start: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """D-1 ``_PUBLISH_HOUR_LOCAL:_PUBLISH_MINUTE_LOCAL`` Europe/Paris, converted to UTC.

    Approximated convention (no publication timestamp in the API): see the module docstring
    and ``core.storage.energy_store`` for the rationale.
    """
    day_ahead = interval_start.tz_convert(_PUBLISH_TZ).floor("D") - pd.Timedelta(days=1)
    publish_local = day_ahead + pd.Timedelta(
        hours=_PUBLISH_HOUR_LOCAL, minutes=_PUBLISH_MINUTE_LOCAL
    )
    return publish_local.tz_convert("UTC")


#: Bounded retry for transient ENTSO-E hiccups (observed empirically: an isolated call for a
#: chunk that just failed routinely succeeds on immediate retry -- not a real data gap).
_MAX_ATTEMPTS = 3
_RETRY_BACKOFF_SECONDS = 5.0


class _NoDataInRange(Exception):
    """Raised (internal) when a zone genuinely has no day-ahead data in a chunk's range."""


def _query_with_retry(
    client: DayAheadClient, zone: str, start: pd.Timestamp, end: pd.Timestamp
) -> pd.Series:
    """Retries transient failures; re-raises ``NoMatchingDataError`` as :class:`_NoDataInRange`
    once retries are exhausted (a real reporting gap, not a hiccup -- observed empirically:
    an isolated retry of a freshly-failed chunk routinely succeeds, so persistence past
    ``_MAX_ATTEMPTS`` is treated as a genuine gap, not transient flakiness)."""
    last_error: Exception | None = None
    for attempt in range(_MAX_ATTEMPTS):
        try:
            return client.query_day_ahead_prices(zone, start=start, end=end)
        except Exception as exc:  # noqa: BLE001 - retried, then classified below
            last_error = exc
            if attempt < _MAX_ATTEMPTS - 1:
                time.sleep(_RETRY_BACKOFF_SECONDS * (attempt + 1))
    assert last_error is not None  # loop always runs >=1 attempt
    if type(last_error).__name__ == "NoMatchingDataError":
        raise _NoDataInRange from last_error
    raise last_error


def extract_long(client: DayAheadClient, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Extracts FR + DE day-ahead prices over [start, end] in energy long format (UTC).

    A zone with no data in this range (confirmed gap, not transient -- see
    :func:`_query_with_retry`) is skipped with a warning, not a hard failure: real ENTSO-E
    history has occasional reporting holes, and skipping one zone/chunk must not abort the
    whole backfill.
    """
    frames: list[pd.DataFrame] = []
    for zone, source in _ZONES.items():
        try:
            series = _query_with_retry(client, zone, start, end)
        except _NoDataInRange:
            log.warning(
                "No ENTSO-E day-ahead data for %s in [%s, %s) -- skipping this chunk.",
                zone,
                start,
                end,
            )
            continue
        index_utc = pd.DatetimeIndex(series.index).tz_convert("UTC")
        frames.append(
            pd.DataFrame(
                {
                    SOURCE: source,
                    SERIES: _SERIES_NAME,
                    PUBLISH_TIME: _approximate_publish_time(index_utc),
                    INTERVAL_START: index_utc,
                    VALUE: series.to_numpy(dtype=float),
                }
            )
        )
    if not frames:
        return pd.DataFrame(columns=[SOURCE, SERIES, PUBLISH_TIME, INTERVAL_START, VALUE])
    return pd.concat(frames, ignore_index=True)


def backfill(
    client: DayAheadClient,
    store: EnergyColdStore,
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
    *,
    chunk_days: int = 30,
) -> tuple[int, int]:
    """Backfills [start, end] in monthly chunks; returns (rows written, API calls made).

    ``API calls made`` counts one call per (chunk, zone) attempted, including chunks that
    turned out to have no data -- an honest count of network traffic consumed, not just
    successful pulls.
    """
    total_rows = 0
    total_calls = 0
    cursor = pd.Timestamp(start, tz="UTC")
    stop = pd.Timestamp(end, tz="UTC")
    step = pd.Timedelta(days=chunk_days)
    while cursor < stop:
        chunk_end = min(cursor + step, stop)
        total_rows += store.write(extract_long(client, cursor, chunk_end))
        total_calls += len(_ZONES)
        cursor = chunk_end
    return total_rows, total_calls


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", required=True, help="Range start (e.g. 2024-01-01).")
    parser.add_argument("--end", required=True, help="Range end, exclusive (e.g. 2025-01-01).")
    parser.add_argument("--chunk-days", type=int, default=30, help="Chunk size (days).")
    parser.add_argument(
        "--store-path",
        default="data/cold/energy",
        help="Energy cold store directory (default: data/cold/energy).",
    )
    return parser.parse_args()


def main() -> None:  # pragma: no cover (operational, requires the API token + network)
    """Operational entry point. Range and destination are configurable on the command line."""
    from entsoe import EntsoePandasClient  # noqa: PLC0415

    args = _parse_args()
    token = os.environ.get("ENTSOE_API_TOKEN")
    if not token:
        raise RuntimeError("ENTSOE_API_TOKEN must be set (see .env.example).")
    client = EntsoePandasClient(api_key=token)
    store = EnergyColdStore(Path(args.store_path))
    rows, calls = backfill(client, store, args.start, args.end, chunk_days=args.chunk_days)
    print(f"{rows} rows written to {args.store_path} (plain git); {calls} ENTSO-E API calls made.")


if __name__ == "__main__":  # pragma: no cover
    main()
