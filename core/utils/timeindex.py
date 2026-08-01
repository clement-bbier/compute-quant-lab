"""Validation and normalisation of time indexes (UTC, timezone-aware).

Single home for the lab's data-integrity rule: *every timestamp is UTC and
timezone-aware; no naive datetime is ever accepted*. Consumed by the price
sources and FX converters in :mod:`core.pricing` and by the point-in-time
feature builders in :mod:`core.features`, so the boundary is defined and
tested exactly once.
"""

from __future__ import annotations

import pandas as pd

__all__ = ["to_utc_index"]


def to_utc_index(index: pd.Index) -> pd.DatetimeIndex:
    """Check that an index is a tz-aware datetime index and convert it to UTC.

    Parameters
    ----------
    index
        Index to validate.

    Returns
    -------
    pandas.DatetimeIndex
        The same index converted to UTC.

    Raises
    ------
    ValueError
        If ``index`` is not a :class:`~pandas.DatetimeIndex`, or if it is
        timezone-naive.
    """
    if not isinstance(index, pd.DatetimeIndex):
        raise ValueError("index must be a DatetimeIndex.")
    if index.tz is None:
        raise ValueError("index must be timezone-aware (UTC); naive datetimes are rejected.")
    return index.tz_convert("UTC")
