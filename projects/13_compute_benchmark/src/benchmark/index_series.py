"""**Point-in-time** compute spot index series on the cold store.

:func:`build_index_series` samples the canonical index
(:func:`core.ingestion.build_spot_index`) on a grid of fix instants. The
*published product* granularity is the **daily fix** (:func:`daily_fix_grid`,
00:30 UTC, analogous to the GPU Markets fix); the demo dashboard can render a finer
cadence without changing the method.

Point-in-time guarantee: inherited from ``build_spot_index`` (no observation ``> as_of``
enters a fix). Sparse-data robustness: a fix without a fresh venue is **skipped
and recorded** (``IndexSeries.skipped``), never invented via carry-forward.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Sequence

import pandas as pd

from core.ingestion.compute_index import (
    DEFAULT_INDEX_CONFIG,
    IndexConfig,
    InsufficientDataError,
    build_spot_index,
)
from core.ingestion.protocols import Snapshot, SpotIndexPoint, ensure_utc

#: Time of the canonical daily fix (UTC) — analogous to the GPU Markets 00:30 fix.
DEFAULT_FIX_TIME = dt.time(0, 30)

#: Auditable columns exposed by :meth:`IndexSeries.to_frame`.
_FRAME_COLUMNS = [
    "as_of",
    "gpu_model",
    "price_usd_per_hour",
    "n_sources",
    "method",
    "oldest_obs_at",
]


def daily_fix_grid(
    start: dt.datetime, end: dt.datetime, fix_time: dt.time = DEFAULT_FIX_TIME
) -> list[dt.datetime]:
    """Lists the daily fix instants (``fix_time`` UTC) within ``[start, end]``.

    Parameters
    ----------
    start, end
        UTC tz-aware bounds (a naive datetime is rejected — point-in-time integrity).
    fix_time
        Time of the fix within the day (default 00:30 UTC).

    Returns
    -------
    list[datetime.datetime]
        One instant per calendar day falling within ``[start, end]`` (bounds included).
    """
    start, end = ensure_utc(start), ensure_utc(end)
    grid: list[dt.datetime] = []
    day = start.date()
    while day <= end.date():
        candidate = dt.datetime.combine(day, fix_time, tzinfo=dt.timezone.utc)
        if start <= candidate <= end:
            grid.append(candidate)
        day += dt.timedelta(days=1)
    return grid


def observed_fix_grid(
    snapshots: Sequence[Snapshot], *, gpu_model: str | None = None
) -> list[dt.datetime]:
    """**Demo** cadence: distinct observed snapshot instants, sorted.

    Used to render a curve over the thin real history (fine cadence, labeled demo),
    where the canonical daily fix would only produce a single point. Optionally filtered by
    ``gpu_model``.
    """
    times = {s.snapshotted_at for s in snapshots if gpu_model is None or s.gpu_model == gpu_model}
    return sorted(times)


@dataclass(frozen=True)
class IndexSeries:
    """Canonical index series for a GPU model + skipped fixes (sparse data).

    ``points`` is the computed series (an auditable :class:`SpotIndexPoint` per fix);
    ``skipped`` lists the ``as_of`` values without a fresh venue — the thin history is explicit,
    never filled by carry-forward.
    """

    gpu_model: str
    points: list[SpotIndexPoint]
    skipped: list[dt.datetime]

    def to_frame(self) -> pd.DataFrame:
        """Serializes ``points`` into an auditable DataFrame (columns :data:`_FRAME_COLUMNS`)."""
        rows = [
            {
                "as_of": p.as_of,
                "gpu_model": p.gpu_model,
                "price_usd_per_hour": p.price_usd_per_hour,
                "n_sources": p.n_sources,
                "method": p.method,
                "oldest_obs_at": p.oldest_obs_at,
            }
            for p in self.points
        ]
        return pd.DataFrame(rows, columns=_FRAME_COLUMNS)


def build_index_series(
    snapshots: Sequence[Snapshot],
    as_of_grid: Sequence[dt.datetime],
    gpu_model: str,
    *,
    config: IndexConfig = DEFAULT_INDEX_CONFIG,
) -> IndexSeries:
    """Samples the canonical index of ``gpu_model`` over ``as_of_grid``.

    Each ``as_of`` produces a fix via ``build_spot_index``; a fix without a fresh venue
    (``InsufficientDataError``) is recorded in ``skipped`` rather than filled.

    Parameters
    ----------
    snapshots
        Raw multi-venue readings (filtered by ``build_spot_index``).
    as_of_grid
        Fix instants (UTC) — typically produced by :func:`daily_fix_grid`.
    gpu_model
        Aggregated model (e.g. ``"H100"``).
    config
        Aggregation strategy (default: market standard).

    Returns
    -------
    IndexSeries
        Computed points + skipped ``as_of`` values (sparse data).
    """
    points: list[SpotIndexPoint] = []
    skipped: list[dt.datetime] = []
    for as_of in as_of_grid:
        try:
            points.append(build_spot_index(snapshots, as_of, gpu_model, config=config))
        except InsufficientDataError:
            skipped.append(ensure_utc(as_of))
    return IndexSeries(gpu_model=gpu_model, points=points, skipped=skipped)
