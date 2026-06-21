"""Alignement temporel / fuseau (§6b).

Les données macro arrivent en fuseaux variés ; toute comparaison « connu à t » doit
se faire en UTC tz-aware. On rejette le datetime naïf (ambigu), on normalise les
fuseaux, et on vérifie que la frontière as-of est *inclusive* (knowledge_ts == asof
est connu) — pas de décalage d'un cran.
"""

from __future__ import annotations

import pandas as pd
import pytest

from core.features.builders import as_of_snapshot, from_lagged_series


def test_naive_datetime_index_is_rejected():
    s = pd.Series([1.0, 2.0], index=pd.DatetimeIndex(["2025-01-01", "2025-01-02"]))  # tz-naïf
    with pytest.raises(ValueError):
        from_lagged_series(s, pd.Timedelta("1D"))


def test_non_utc_timezone_is_normalised_to_utc():
    # 2025-01-01 00:00 Europe/Paris (UTC+1 en hiver) = 2024-12-31 23:00 UTC.
    idx = pd.DatetimeIndex(["2025-01-01 00:00", "2025-01-02 00:00"], tz="Europe/Paris")
    vintages = from_lagged_series(pd.Series([100.0, 200.0], index=idx), pd.Timedelta("0D"))

    snap = as_of_snapshot(vintages, pd.Timestamp("2024-12-31 23:00", tz="UTC"))
    assert snap.index[0] == pd.Timestamp("2024-12-31 23:00", tz="UTC")
    assert snap.iloc[0] == 100.0


def test_asof_boundary_is_inclusive(day_ts):
    # knowledge_ts == asof doit être considéré connu (<=, pas <).
    s = pd.Series([100.0], index=pd.DatetimeIndex([day_ts(0)]))
    vintages = from_lagged_series(s, pd.Timedelta("2D"))  # connu à D2
    snap = as_of_snapshot(vintages, day_ts(2))  # asof == knowledge_ts
    assert list(snap.index) == [day_ts(0)]
    assert snap.loc[day_ts(0)] == 100.0
