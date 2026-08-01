"""Benchmark assembly: per model (index + dispersion + levels) + honest history state.

Pure layer, shared by ``run_build_benchmark.py`` (MLflow run + ``results/`` writing)
and ``dashboard/app.py`` (Streamlit rendering) — so they stay thin and consistent (DRY).
``summarize_history`` makes explicit the **thinness** of the accumulated compute history
(number of readings, venues, time span), consistent with the framing "acknowledge that
the index is thin at the start, it grows".
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from dataclasses import dataclass
from typing import Sequence

from benchmark.dispersion import DispersionPoint, VenueLevel, dispersion_at, venue_levels
from benchmark.index_series import IndexSeries, build_index_series
from core.ingestion.compute_index import DEFAULT_INDEX_CONFIG, IndexConfig
from core.ingestion.protocols import Snapshot


@dataclass(frozen=True)
class HistoryState:
    """Honest snapshot of the accumulated real history (so nothing is oversold)."""

    n_snapshots: int
    n_venues: int
    sources: tuple[str, ...]
    n_distinct_timestamps: int
    span_hours: float
    first_at: dt.datetime | None
    last_at: dt.datetime | None


@dataclass(frozen=True)
class ModelBenchmark:
    """Complete benchmark for a GPU model: index series, per-fix dispersion, venue levels."""

    gpu_model: str
    index: IndexSeries
    dispersion: list[DispersionPoint]
    venue_levels: list[VenueLevel]


@dataclass(frozen=True)
class BenchmarkReport:
    """Overall multi-model result + state of the underlying history."""

    models: list[ModelBenchmark]
    history: HistoryState
    fix_times: list[dt.datetime]

    def mean_spread_pct(self) -> float | None:
        """Mean cross-venue spread % over all fixes where dispersion is defined."""
        defined = [
            d.spread_pct
            for m in self.models
            for d in m.dispersion
            if d.is_defined and d.spread_pct is not None
        ]
        return sum(defined) / len(defined) if defined else None


def summarize_history(snapshots: Sequence[Snapshot]) -> HistoryState:
    """Summarizes the history: number of readings, named venues, distinct instants, time span."""
    if not snapshots:
        return HistoryState(0, 0, (), 0, 0.0, None, None)
    times = [s.snapshotted_at for s in snapshots]
    first_at, last_at = min(times), max(times)
    sources = tuple(sorted({s.source for s in snapshots}))
    return HistoryState(
        n_snapshots=len(snapshots),
        n_venues=len(sources),
        sources=sources,
        n_distinct_timestamps=len(set(times)),
        span_hours=(last_at - first_at).total_seconds() / 3600.0,
        first_at=first_at,
        last_at=last_at,
    )


def multi_venue_models(snapshots: Sequence[Snapshot], *, min_venues: int = 2) -> list[str]:
    """Models present in ``>= min_venues`` venues (candidates for dispersion)."""
    venues_by_model: dict[str, set[str]] = defaultdict(set)
    for s in snapshots:
        venues_by_model[s.gpu_model].add(s.source)
    return sorted(m for m, venues in venues_by_model.items() if len(venues) >= min_venues)


def build_report(
    snapshots: Sequence[Snapshot],
    models: Sequence[str],
    grid: Sequence[dt.datetime],
    *,
    config: IndexConfig = DEFAULT_INDEX_CONFIG,
) -> BenchmarkReport:
    """Assembles the benchmark for ``models`` over the ``grid`` (dispersion aligned with the index)."""
    model_benchmarks: list[ModelBenchmark] = []
    for model in models:
        index = build_index_series(snapshots, grid, model, config=config)
        # Dispersion computed only at fixes that produced an index point
        # (strict alignment + no exception on sparse windows).
        dispersion = [
            dispersion_at(snapshots, point.as_of, model, config=config) for point in index.points
        ]
        levels = venue_levels(snapshots, grid, model, config=config)
        model_benchmarks.append(
            ModelBenchmark(gpu_model=model, index=index, dispersion=dispersion, venue_levels=levels)
        )
    return BenchmarkReport(
        models=model_benchmarks,
        history=summarize_history(snapshots),
        fix_times=list(grid),
    )
