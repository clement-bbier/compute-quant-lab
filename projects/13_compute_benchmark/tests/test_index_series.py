"""Tests for the point-in-time index series (fix grid + canonical aggregation)."""

from __future__ import annotations

import datetime as dt

import pytest

from benchmark.index_series import (
    IndexSeries,
    build_index_series,
    daily_fix_grid,
    observed_fix_grid,
)
from core.ingestion.protocols import Snapshot


def test_daily_fix_grid_one_instant_per_day(fix_day1, fix_day2) -> None:
    # Two instants aligned on 00:30 UTC → one fix per day, bounds included.
    grid = daily_fix_grid(fix_day1, fix_day2)
    assert grid == [fix_day1, fix_day2]


def test_daily_fix_grid_excludes_instants_outside_range(fix_day1, fix_day2) -> None:
    # Window starting after the D-1 fix: that fix falls out of range, only D remains.
    grid = daily_fix_grid(fix_day1 + dt.timedelta(hours=1), fix_day2)
    assert grid == [fix_day2]


def test_daily_fix_grid_rejects_naive_bounds() -> None:
    # UTC discipline: a naive datetime is rejected (point-in-time integrity).
    with pytest.raises(ValueError):
        daily_fix_grid(dt.datetime(2026, 6, 20, 0, 30), dt.datetime(2026, 6, 21, 0, 30))


def test_build_series_matches_known_prices(two_day_snapshots, fix_day1, fix_day2) -> None:
    series = build_index_series(two_day_snapshots, [fix_day1, fix_day2], "H100")
    assert isinstance(series, IndexSeries)
    assert [p.price_usd_per_hour for p in series.points] == pytest.approx([2.10, 2.20])
    assert [p.n_sources for p in series.points] == [2, 2]
    assert series.skipped == []


def test_series_skips_fixes_without_data(two_day_snapshots, fix_day1, fix_day2) -> None:
    # Sparse-data robustness: a fix earlier than any reading is skipped, not invented.
    empty_fix = fix_day1 - dt.timedelta(days=1)
    series = build_index_series(two_day_snapshots, [empty_fix, fix_day1, fix_day2], "H100")
    assert series.skipped == [empty_fix]
    assert [p.as_of for p in series.points] == [fix_day1, fix_day2]


def test_no_lookahead_future_snapshot_leaves_past_fixes_unchanged(
    two_day_snapshots, fix_day1, fix_day2
) -> None:
    # A reading after the last fix must not modify ANY earlier fix.
    leak = Snapshot(fix_day2 + dt.timedelta(hours=5), "vastai", "H100", 99.0)
    base = build_index_series(two_day_snapshots, [fix_day1, fix_day2], "H100")
    after = build_index_series([*two_day_snapshots, leak], [fix_day1, fix_day2], "H100")
    assert [p.price_usd_per_hour for p in after.points] == pytest.approx(
        [p.price_usd_per_hour for p in base.points]
    )


def test_observed_fix_grid_returns_sorted_distinct_timestamps(two_day_snapshots) -> None:
    # Demo cadence: one instant per observed snapshot cohort, sorted (anti-duplicate).
    grid = observed_fix_grid(two_day_snapshots)
    assert grid == sorted({s.snapshotted_at for s in two_day_snapshots})
    assert len(grid) == 2


def test_observed_fix_grid_can_filter_by_model() -> None:
    ts = dt.datetime(2026, 6, 21, 0, 0, tzinfo=dt.timezone.utc)
    snaps = [
        Snapshot(ts, "vastai", "H100", 2.0),
        Snapshot(ts + dt.timedelta(hours=1), "vastai", "A100", 1.0),
    ]
    assert observed_fix_grid(snaps, gpu_model="H100") == [ts]


def test_to_frame_exposes_auditable_columns(two_day_snapshots, fix_day1, fix_day2) -> None:
    series = build_index_series(two_day_snapshots, [fix_day1, fix_day2], "H100")
    frame = series.to_frame()
    assert list(frame.columns) == [
        "as_of",
        "gpu_model",
        "price_usd_per_hour",
        "n_sources",
        "method",
        "oldest_obs_at",
    ]
    assert len(frame) == len(series.points) == 2
