"""Tests for the ERCOT "RTM spike" label builder (L0 spec §4-§5)."""

from __future__ import annotations

import pandas as pd

from ercot_labels import (
    spike_label_absolute,
    spike_label_hod_percentile,
    to_hourly_integrated,
)


def _daily_at_hour(hour: int, prices: list[float], start: str = "2024-01-01") -> pd.Series:
    days = pd.date_range(start, periods=len(prices), freq="1D", tz="UTC")
    return pd.Series(prices, index=days + pd.Timedelta(hours=hour))


def test_to_hourly_integrated_means_subhourly() -> None:
    idx = pd.date_range("2024-01-01", periods=8, freq="15min", tz="UTC")
    s = pd.Series([10.0, 20.0, 30.0, 40.0, 100.0, 100.0, 100.0, 100.0], index=idx)
    hourly = to_hourly_integrated(s)
    assert list(hourly.to_numpy()) == [25.0, 100.0]  # average of the 4 quarter-hours


def test_spike_label_absolute() -> None:
    idx = pd.date_range("2024-01-01", periods=3, freq="1h", tz="UTC")
    s = pd.Series([100.0, 1600.0, 1499.0], index=idx)
    assert list(spike_label_absolute(s, threshold_usd_mwh=1500.0).to_numpy()) == [
        False,
        True,
        False,
    ]


def test_hod_percentile_insufficient_history_is_false() -> None:
    s = _daily_at_hour(18, [50.0, 60.0, 5000.0])  # < 3 past obs everywhere
    lab = spike_label_hod_percentile(s, pct=0.99, min_obs_per_hour=3)
    assert not lab.any()


def test_hod_percentile_flags_spike_vs_past_same_hour() -> None:
    s = _daily_at_hour(18, [50.0] * 10 + [5000.0])  # 10 calm days then a spike
    lab = spike_label_hod_percentile(s, pct=0.99, min_obs_per_hour=3)
    assert lab.iloc[-1]  # spike flagged (5000 >> 99th pct of the ~50 past)
    assert not lab.iloc[:-1].any()  # no calm day flagged


def test_hod_percentile_is_causal_no_lookahead() -> None:
    # A FUTURE spike must not influence the label of an earlier calm day.
    s = _daily_at_hour(18, [50.0, 50.0, 50.0, 50.0, 5000.0, 50.0])
    lab = spike_label_hod_percentile(s, pct=0.99, min_obs_per_hour=3)
    assert not lab.iloc[3]  # calm day: does not see day 4's spike
    assert lab.iloc[4]  # the spike, vs the calm past, is flagged
    assert not lab.iloc[5]  # calm=50; the past includes the spike -> high threshold -> not a spike
