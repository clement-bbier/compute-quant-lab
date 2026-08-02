"""Pure logic for the gpu-price MCP server (no MCP dependency).

Each function receives an injected :class:`~core.storage.protocols.PriceStore` and returns a
JSON-serializable dict/list. Point-in-time filtering goes through ``as_of`` (ISO 8601 UTC,
naive instants rejected). The prices served are **real** (observed spot): every response
carries ``provenance="real"``.
"""

from __future__ import annotations

import datetime as dt
import statistics
from typing import Any

import pandas as pd

from core.storage import query as duckdb_query
from core.storage.parquet_store import ParquetPriceStore
from core.storage.protocols import PriceStore

#: Real/simulated label (forward-real-simulated.md rule) — this server only ever serves real data.
PROVENANCE = "real"


def _parse_instant(value: str | None) -> dt.datetime | None:
    """Parse an ISO 8601 instant into a tz-aware UTC datetime; ``None`` stays ``None``.

    Raises
    ------
    ValueError
        If ``value`` is not a valid ISO 8601 string, or if it is naive (no timezone).
    """
    if value is None:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            f"Invalid ISO 8601 instant: {value!r}. Example: '2026-06-21T00:00:00+00:00'."
        ) from exc
    if parsed.tzinfo is None:
        raise ValueError(
            f"Naive instant not allowed: {value!r}. Provide a tz-aware UTC instant "
            "(e.g. '2026-06-21T00:00:00+00:00')."
        )
    return parsed.astimezone(dt.timezone.utc)


def list_gpu_models(store: PriceStore, *, as_of: str | None = None) -> list[str]:
    """Sorted list of GPU models present in the lake (bounded to ``snapshotted_at <= as_of``)."""
    frame = store.read(as_of=_parse_instant(as_of))
    if frame.empty:
        return []
    return sorted(frame["gpu_model"].unique().tolist())


def _latest_row_per_source(subset: pd.DataFrame) -> pd.DataFrame:
    """Per source: the most recent instant, then the cheapest offer at that instant."""
    freshest_per_source = subset.groupby("source")["snapshotted_at"].transform("max")
    freshest = subset[subset["snapshotted_at"] == freshest_per_source]
    cheapest_idx = freshest.groupby("source")["price_usd_per_hour"].idxmin()
    return freshest.loc[cheapest_idx].sort_values("source")


def latest_price(
    store: PriceStore,
    gpu_model: str,
    *,
    lease_type: str = "on_demand",
    as_of: str | None = None,
) -> dict[str, Any]:
    """Latest price per source for ``gpu_model``/``lease_type`` (real) + min/median/max summary."""
    cutoff = _parse_instant(as_of)
    frame = store.read(as_of=cutoff)
    subset = frame[(frame["gpu_model"] == gpu_model) & (frame["lease_type"] == lease_type)]
    if subset.empty:
        available = sorted(frame["gpu_model"].unique().tolist()) if not frame.empty else []
        return {
            "gpu_model": gpu_model,
            "lease_type": lease_type,
            "found": False,
            "provenance": PROVENANCE,
            "message": f"No readings for gpu_model={gpu_model!r}, lease_type={lease_type!r}.",
            "available_models": available,
        }
    latest = _latest_row_per_source(subset)
    by_source = [
        {
            "source": row.source,
            "price_usd_per_hour": float(row.price_usd_per_hour),
            "availability": int(row.availability),
            "snapshotted_at": row.snapshotted_at.isoformat(),
        }
        for row in latest.itertuples(index=False)
    ]
    prices = [item["price_usd_per_hour"] for item in by_source]
    return {
        "gpu_model": gpu_model,
        "lease_type": lease_type,
        "found": True,
        "provenance": PROVENANCE,
        "as_of": cutoff.isoformat()
        if cutoff is not None
        else subset["snapshotted_at"].max().isoformat(),
        "by_source": by_source,
        "summary": {
            "min": min(prices),
            "median": round(
                statistics.median(prices), 10
            ),  # round: avoids IEEE-754 artifacts in the float median of 2 prices (e.g. 1.95)
            "max": max(prices),
            "n_sources": len(prices),
        },
    }


def price_history(
    store: PriceStore,
    gpu_model: str,
    *,
    start: str | None = None,
    as_of: str | None = None,
    source: str | None = None,
    lease_type: str | None = None,
) -> dict[str, Any]:
    """Ordered time series of readings (real) for ``gpu_model`` within ``[start, as_of]``."""
    cutoff = _parse_instant(as_of)
    start_dt = _parse_instant(start)
    frame = store.read(as_of=cutoff, source=source)
    subset = frame[frame["gpu_model"] == gpu_model]
    if lease_type is not None:
        subset = subset[subset["lease_type"] == lease_type]
    if start_dt is not None:
        subset = subset[subset["snapshotted_at"] >= pd.Timestamp(start_dt)]
    subset = subset.sort_values("snapshotted_at")
    observations = [
        {
            "snapshotted_at": row.snapshotted_at.isoformat(),
            "source": row.source,
            "lease_type": row.lease_type,
            "price_usd_per_hour": float(row.price_usd_per_hour),
            "availability": int(row.availability),
        }
        for row in subset.itertuples(index=False)
    ]
    return {
        "gpu_model": gpu_model,
        "start": start_dt.isoformat() if start_dt is not None else None,
        "as_of": cutoff.isoformat()
        if cutoff is not None
        else (subset["snapshotted_at"].max().isoformat() if not subset.empty else None),
        "provenance": PROVENANCE,
        "n": len(observations),
        "observations": observations,
    }


def summary_stats(
    store: PriceStore,
    gpu_model: str,
    *,
    lease_type: str | None = None,
    as_of: str | None = None,
) -> dict[str, Any]:
    """Descriptive stats (real) for ``gpu_model`` prices, bounded to the point-in-time ``as_of``."""
    cutoff = _parse_instant(as_of)
    frame = store.read(as_of=cutoff)
    subset = frame[frame["gpu_model"] == gpu_model]
    if lease_type is not None:
        subset = subset[subset["lease_type"] == lease_type]
    if subset.empty:
        return {
            "gpu_model": gpu_model,
            "found": False,
            "provenance": PROVENANCE,
            "n": 0,
            "message": f"No readings for gpu_model={gpu_model!r}.",
        }
    prices = subset["price_usd_per_hour"]
    overall = {
        "count": int(prices.count()),
        "min": float(prices.min()),
        "max": float(prices.max()),
        "mean": float(prices.mean()),
        "median": float(prices.median()),
        "std": float(prices.std(ddof=0)),  # population: well-defined even for n=1
    }
    by_source = [
        {
            "source": str(src),
            "count": int(grp["price_usd_per_hour"].count()),
            "min": float(grp["price_usd_per_hour"].min()),
            "max": float(grp["price_usd_per_hour"].max()),
            "mean": float(grp["price_usd_per_hour"].mean()),
            "median": float(grp["price_usd_per_hour"].median()),
        }
        for src, grp in subset.groupby("source")
    ]
    return {
        "gpu_model": gpu_model,
        "found": True,
        "provenance": PROVENANCE,
        "as_of": cutoff.isoformat()
        if cutoff is not None
        else subset["snapshotted_at"].max().isoformat(),
        "n": int(prices.count()),
        "overall": overall,
        "by_source": sorted(by_source, key=lambda d: d["source"]),
        "first_obs_at": subset["snapshotted_at"].min().isoformat(),
        "last_obs_at": subset["snapshotted_at"].max().isoformat(),
    }


def _jsonable(value: Any) -> Any:
    """Make a DuckDB/pandas value JSON-serializable (Timestamp->ISO UTC, NaN->None, numpy->python).

    DuckDB renders ``TIMESTAMP WITH TIME ZONE`` columns in the process's local timezone;
    we renormalize to UTC to stay consistent with the structured tools (lab UTC rule).
    """
    if isinstance(value, pd.Timestamp):
        if value.tzinfo is not None:
            value = value.tz_convert("UTC")
        return value.isoformat()
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        # pd.isna raises on non-scalars (list, array): not a NaN, fall through.
        pass
    if hasattr(value, "item"):  # numpy scalars
        return value.item()
    return value


def run_query(store: ParquetPriceStore, sql: str) -> dict[str, Any]:
    """Run ``sql`` (**raw** DuckDB) against the lake's ``prices`` view. No point-in-time guard.

    Requires a concrete ``ParquetPriceStore`` (DuckDB needs ``store.root``);
    the other functions accept any ``PriceStore``.
    """
    frame = duckdb_query(sql, store)
    rows = [
        {k: _jsonable(v) for k, v in record.items()} for record in frame.to_dict(orient="records")
    ]
    return {
        "columns": list(frame.columns),
        "rows": rows,
        "n": len(rows),
        "note": "Raw DuckDB SQL — NO point-in-time guard; as_of filtering is the caller's responsibility.",
    }
