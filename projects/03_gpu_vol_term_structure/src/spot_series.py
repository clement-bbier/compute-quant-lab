"""Construction of a compute spot index time series (core consumer).

P03 needs a **series** of spot prices to estimate volatility, whereas
``core.ingestion.build_spot_index`` produces a single fix per ``as_of``. This module
replays the index builder over a fix grid, remaining strictly
**point-in-time** (each fix uses only ``snapshotted_at <= as_of``, guaranteed by
``build_spot_index``) and ignoring instants with no fresh data (no carry-forward).

Pure consumer of ``core/`` (read-only): no aggregation logic is duplicated here.
"""

from __future__ import annotations

import datetime as dt
from typing import Sequence

import numpy as np

from core.ingestion import (
    DEFAULT_INDEX_CONFIG,
    IndexConfig,
    InsufficientDataError,
    Snapshot,
    build_spot_index,
)


def build_spot_series(
    snapshots: Sequence[Snapshot],
    as_of_grid: Sequence[dt.datetime],
    gpu_model: str,
    *,
    config: IndexConfig = DEFAULT_INDEX_CONFIG,
) -> tuple[list[dt.datetime], np.ndarray]:
    """Spot index series over ``as_of_grid`` (unresolvable instants are ignored).

    Parameters
    ----------
    snapshots
        Raw readings (all sources/models combined).
    as_of_grid
        Grid of fix instants (UTC), preferably increasing.
    gpu_model
        Aggregated model (e.g. ``"H100"``).
    config
        Injectable aggregation config (default: market standard).

    Returns
    -------
    tuple[list[datetime], numpy.ndarray]
        The instants actually resolved and the corresponding $/GPU·h prices. An
        instant with no fresh reading (``InsufficientDataError``) is **omitted** (not fabricated).
    """
    times: list[dt.datetime] = []
    prices: list[float] = []
    for as_of in as_of_grid:
        try:
            point = build_spot_index(snapshots, as_of, gpu_model, config=config)
        except InsufficientDataError:
            continue
        times.append(point.as_of)
        prices.append(point.price_usd_per_hour)
    return times, np.asarray(prices, dtype=float)
