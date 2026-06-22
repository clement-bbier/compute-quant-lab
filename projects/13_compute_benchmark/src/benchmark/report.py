"""Assemblage du benchmark : par modèle (indice + dispersion + niveaux) + état honnête de l'historique.

Couche pure, partagée par ``run_build_benchmark.py`` (run MLflow + écriture ``results/``)
et ``dashboard/app.py`` (rendu Streamlit) — pour qu'ils restent minces et cohérents (DRY).
``summarize_history`` rend explicite la **maigreur** de l'historique compte accumulé
(nombre de relevés, de venues, span temporel), conformément au cadrage « assumer que
l'indice est maigre au début, il grossit ».
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
    """Photo honnête de l'historique réel accumulé (pour ne rien survendre)."""

    n_snapshots: int
    n_venues: int
    sources: tuple[str, ...]
    n_distinct_timestamps: int
    span_hours: float
    first_at: dt.datetime | None
    last_at: dt.datetime | None


@dataclass(frozen=True)
class ModelBenchmark:
    """Benchmark complet d'un modèle GPU : série d'indice, dispersion par fix, niveaux venues."""

    gpu_model: str
    index: IndexSeries
    dispersion: list[DispersionPoint]
    venue_levels: list[VenueLevel]


@dataclass(frozen=True)
class BenchmarkReport:
    """Résultat global multi-modèles + état de l'historique sous-jacent."""

    models: list[ModelBenchmark]
    history: HistoryState
    fix_times: list[dt.datetime]

    def mean_spread_pct(self) -> float | None:
        """Spread % inter-venues moyen sur tous les fix où la dispersion est définie."""
        defined = [
            d.spread_pct
            for m in self.models
            for d in m.dispersion
            if d.is_defined and d.spread_pct is not None
        ]
        return sum(defined) / len(defined) if defined else None


def summarize_history(snapshots: Sequence[Snapshot]) -> HistoryState:
    """Résume l'historique : nb de relevés, venues nommées, instants distincts, span horaire."""
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
    """Modèles présents dans ``>= min_venues`` venues (candidats à la dispersion)."""
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
    """Assemble le benchmark de ``models`` sur la grille ``grid`` (dispersion alignée sur l'indice)."""
    model_benchmarks: list[ModelBenchmark] = []
    for model in models:
        index = build_index_series(snapshots, grid, model, config=config)
        # Dispersion calculée uniquement aux fix qui ont produit un point d'indice
        # (alignement strict + aucune exception sur les fenêtres creuses).
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
