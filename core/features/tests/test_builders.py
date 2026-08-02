"""Pure transforms + builder on known fixtures.

The transforms (`lag`, `rolling_mean`, `diff`) operate on the *already* point-in-time
snapshot (so all of them are <= t by construction). They are checked against
hand-computed series, then the panel is assembled via `PointInTimeFeatureBuilder`.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from core.features.builders import (
    FeatureSpec,
    PointInTimeFeatureBuilder,
    diff_feature,
    lag_feature,
    rolling_mean_feature,
)


def _snapshot(day_ts) -> pd.Series:
    idx = pd.DatetimeIndex([day_ts(i) for i in range(4)])
    return pd.Series([10.0, 11.0, 12.0, 13.0], index=idx)


def test_lag_feature_returns_kth_most_recent(day_ts):
    snap = _snapshot(day_ts)
    assert lag_feature(snap, 0) == 13.0
    assert lag_feature(snap, 1) == 12.0
    assert lag_feature(snap, 3) == 10.0


def test_lag_feature_beyond_history_is_nan(day_ts):
    assert np.isnan(lag_feature(_snapshot(day_ts), 4))


def test_rolling_mean_over_known_values(day_ts):
    assert rolling_mean_feature(_snapshot(day_ts), 3) == 12.0  # mean(11, 12, 13)


def test_rolling_mean_insufficient_history_is_nan(day_ts):
    assert np.isnan(rolling_mean_feature(_snapshot(day_ts), 10))


def test_diff_feature(day_ts):
    snap = _snapshot(day_ts)
    assert diff_feature(snap, 1) == 1.0  # 13 - 12
    assert diff_feature(snap, 3) == 3.0  # 13 - 10


def test_build_panel_shape_names_and_point_in_time(day_ts, make_vintages, fake_source):
    # Variable without lag (knowledge_ts == value_ts) to isolate the builder machinery.
    records = [(day_ts(i), day_ts(i), 10.0 + i) for i in range(4)]
    source = fake_source({"gas_price": make_vintages(records)})
    builder = PointInTimeFeatureBuilder(
        source, {"gas_price": FeatureSpec(lags=(0, 1), rolling_means=(2,))}
    )

    panel = builder.build_panel(pd.DatetimeIndex([day_ts(2), day_ts(3)]))

    assert list(panel.columns) == ["gas_price_lag0", "gas_price_lag1", "gas_price_roll2"]
    assert panel.shape == (2, 3)
    # At D3: known = {10,11,12,13} -> lag0=13, lag1=12, roll2=mean(12,13)=12.5.
    assert panel.loc[day_ts(3), "gas_price_lag0"] == 13.0
    assert panel.loc[day_ts(3), "gas_price_lag1"] == 12.0
    assert panel.loc[day_ts(3), "gas_price_roll2"] == 12.5
    # At D2: known = {10,11,12} -> lag0=12 (not 13: anti look-ahead).
    assert panel.loc[day_ts(2), "gas_price_lag0"] == 12.0
