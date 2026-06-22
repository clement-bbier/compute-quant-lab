"""Tests de la couche d'assemblage (report) : état de l'historique + agrégat multi-modèles."""

from __future__ import annotations

import pytest

from benchmark.report import (
    BenchmarkReport,
    build_report,
    multi_venue_models,
    summarize_history,
)
from core.ingestion.protocols import Snapshot


def test_summarize_history_reports_honest_shape(two_day_snapshots) -> None:
    h = summarize_history(two_day_snapshots)
    assert h.n_snapshots == 4
    assert h.n_venues == 2
    assert h.sources == ("runpod", "vastai")
    assert h.n_distinct_timestamps == 2  # une cohorte par fenêtre de fix
    assert h.span_hours == pytest.approx(24.0)


def test_summarize_history_empty_is_safe() -> None:
    h = summarize_history([])
    assert h.n_snapshots == 0 and h.n_venues == 0
    assert h.first_at is None and h.last_at is None and h.span_hours == 0.0


def test_multi_venue_models_keeps_only_models_in_two_or_more_venues(two_day_snapshots) -> None:
    # H100 est dans deux venues ; un A100 mono-venue ne doit pas remonter.
    solo = Snapshot(two_day_snapshots[0].snapshotted_at, "vastai", "A100", 1.0)
    models = multi_venue_models([*two_day_snapshots, solo])
    assert models == ["H100"]


def test_build_report_assembles_per_model_benchmark(two_day_snapshots, fix_day1, fix_day2) -> None:
    report = build_report(two_day_snapshots, ["H100"], [fix_day1, fix_day2])
    assert isinstance(report, BenchmarkReport)
    assert [m.gpu_model for m in report.models] == ["H100"]
    h100 = report.models[0]
    assert [p.price_usd_per_hour for p in h100.index.points] == pytest.approx([2.10, 2.20])
    assert [d.n_venues for d in h100.dispersion] == [2, 2]
    assert {lv.source for lv in h100.venue_levels} == {"vastai", "runpod"}


def test_mean_spread_pct_averages_defined_dispersion(two_day_snapshots, fix_day1, fix_day2) -> None:
    report = build_report(two_day_snapshots, ["H100"], [fix_day1, fix_day2])
    expected = ((0.20 / 2.10) + (0.20 / 2.20)) / 2
    assert report.mean_spread_pct() == pytest.approx(expected)
