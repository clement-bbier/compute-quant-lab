"""Tests de la série d'indice point-in-time (grille de fix + agrégation canonique)."""

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
    # Deux instants alignés sur 00:30 UTC → un fix par jour, bornes incluses.
    grid = daily_fix_grid(fix_day1, fix_day2)
    assert grid == [fix_day1, fix_day2]


def test_daily_fix_grid_excludes_instants_outside_range(fix_day1, fix_day2) -> None:
    # Fenêtre démarrant après le fix de J-1 : ce fix tombe hors plage, seul J reste.
    grid = daily_fix_grid(fix_day1 + dt.timedelta(hours=1), fix_day2)
    assert grid == [fix_day2]


def test_daily_fix_grid_rejects_naive_bounds() -> None:
    # Discipline UTC : un datetime naïf est refusé (intégrité point-in-time).
    with pytest.raises(ValueError):
        daily_fix_grid(dt.datetime(2026, 6, 20, 0, 30), dt.datetime(2026, 6, 21, 0, 30))


def test_build_series_matches_known_prices(two_day_snapshots, fix_day1, fix_day2) -> None:
    series = build_index_series(two_day_snapshots, [fix_day1, fix_day2], "H100")
    assert isinstance(series, IndexSeries)
    assert [p.price_usd_per_hour for p in series.points] == pytest.approx([2.10, 2.20])
    assert [p.n_sources for p in series.points] == [2, 2]
    assert series.skipped == []


def test_series_skips_fixes_without_data(two_day_snapshots, fix_day1, fix_day2) -> None:
    # Robustesse données creuses : un fix antérieur à tout relevé est sauté, pas inventé.
    empty_fix = fix_day1 - dt.timedelta(days=1)
    series = build_index_series(two_day_snapshots, [empty_fix, fix_day1, fix_day2], "H100")
    assert series.skipped == [empty_fix]
    assert [p.as_of for p in series.points] == [fix_day1, fix_day2]


def test_no_lookahead_future_snapshot_leaves_past_fixes_unchanged(
    two_day_snapshots, fix_day1, fix_day2
) -> None:
    # Un relevé postérieur au dernier fix ne doit modifier AUCUN fix antérieur.
    leak = Snapshot(fix_day2 + dt.timedelta(hours=5), "vastai", "H100", 99.0)
    base = build_index_series(two_day_snapshots, [fix_day1, fix_day2], "H100")
    after = build_index_series([*two_day_snapshots, leak], [fix_day1, fix_day2], "H100")
    assert [p.price_usd_per_hour for p in after.points] == pytest.approx(
        [p.price_usd_per_hour for p in base.points]
    )


def test_observed_fix_grid_returns_sorted_distinct_timestamps(two_day_snapshots) -> None:
    # Cadence démo : un instant par cohorte de snapshot observée, triés (anti-doublons).
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
