"""Tests du builder de label « spike RTM » ERCOT (fiche L0 §4-§5)."""

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
    assert list(hourly.to_numpy()) == [25.0, 100.0]  # moyenne des 4 quarts d'heure


def test_spike_label_absolute() -> None:
    idx = pd.date_range("2024-01-01", periods=3, freq="1h", tz="UTC")
    s = pd.Series([100.0, 1600.0, 1499.0], index=idx)
    assert list(spike_label_absolute(s, threshold_usd_mwh=1500.0).to_numpy()) == [
        False,
        True,
        False,
    ]


def test_hod_percentile_insufficient_history_is_false() -> None:
    s = _daily_at_hour(18, [50.0, 60.0, 5000.0])  # < 3 obs passées partout
    lab = spike_label_hod_percentile(s, pct=0.99, min_obs_per_hour=3)
    assert not lab.any()


def test_hod_percentile_flags_spike_vs_past_same_hour() -> None:
    s = _daily_at_hour(18, [50.0] * 10 + [5000.0])  # 10 jours calmes puis spike
    lab = spike_label_hod_percentile(s, pct=0.99, min_obs_per_hour=3)
    assert lab.iloc[-1]  # spike flaggé (5000 >> 99e pct du passé ~50)
    assert not lab.iloc[:-1].any()  # aucun jour calme flaggé


def test_hod_percentile_is_causal_no_lookahead() -> None:
    # Un spike FUTUR ne doit pas influencer le label d'un jour calme antérieur.
    s = _daily_at_hour(18, [50.0, 50.0, 50.0, 50.0, 5000.0, 50.0])
    lab = spike_label_hod_percentile(s, pct=0.99, min_obs_per_hour=3)
    assert not lab.iloc[3]  # jour calme : ne voit pas le spike du jour 4
    assert lab.iloc[4]  # le spike, vs passé calme, est flaggé
    assert not lab.iloc[5]  # calme=50 ; le passé inclut le spike → seuil haut → pas un spike
