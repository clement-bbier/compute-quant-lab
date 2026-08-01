"""Temporal / timezone alignment (section 6b).

Macro data arrives in various timezones; every "known at t" comparison must happen in
tz-aware UTC. The naive (ambiguous) datetime is rejected, timezones are normalized, and
the as-of boundary is checked to be *inclusive* (knowledge_ts == asof is known) — no
off-by-one shift.
"""

from __future__ import annotations

import pandas as pd
import pytest

from core.features.builders import as_of_snapshot, from_lagged_series


def test_naive_datetime_index_is_rejected():
    s = pd.Series([1.0, 2.0], index=pd.DatetimeIndex(["2025-01-01", "2025-01-02"]))  # tz-naive
    with pytest.raises(ValueError):
        from_lagged_series(s, pd.Timedelta("1D"))


def test_non_utc_timezone_is_normalised_to_utc():
    # 2025-01-01 00:00 Europe/Paris (UTC+1 in winter) = 2024-12-31 23:00 UTC.
    idx = pd.DatetimeIndex(["2025-01-01 00:00", "2025-01-02 00:00"], tz="Europe/Paris")
    vintages = from_lagged_series(pd.Series([100.0, 200.0], index=idx), pd.Timedelta("0D"))

    snap = as_of_snapshot(vintages, pd.Timestamp("2024-12-31 23:00", tz="UTC"))
    assert snap.index[0] == pd.Timestamp("2024-12-31 23:00", tz="UTC")
    assert snap.iloc[0] == 100.0


def test_asof_boundary_is_inclusive(day_ts):
    # knowledge_ts == asof must be considered known (<=, not <).
    s = pd.Series([100.0], index=pd.DatetimeIndex([day_ts(0)]))
    vintages = from_lagged_series(s, pd.Timedelta("2D"))  # known at D2
    snap = as_of_snapshot(vintages, day_ts(2))  # asof == knowledge_ts
    assert list(snap.index) == [day_ts(0)]
    assert snap.loc[day_ts(0)] == 100.0
