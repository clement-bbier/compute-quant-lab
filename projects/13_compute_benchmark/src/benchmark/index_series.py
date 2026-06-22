"""Série d'indice spot compute **point-in-time** sur le cold store.

:func:`build_index_series` échantillonne l'indice canonique
(:func:`core.ingestion.build_spot_index`) sur une grille d'instants de fix. La
granularité *produit publiée* est le **fix quotidien** (:func:`daily_fix_grid`,
00:30 UTC, analogue au fix GPU Markets) ; le dashboard de démo peut rendre une cadence
plus fine sans changer la méthode.

Garantie point-in-time : héritée de ``build_spot_index`` (aucune observation ``> as_of``
n'entre dans un fix). Robustesse données creuses : un fix sans venue fraîche est **sauté
et enregistré** (``IndexSeries.skipped``), jamais inventé par carry-forward.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Sequence

import pandas as pd

from core.ingestion.compute_index import (
    DEFAULT_INDEX_CONFIG,
    IndexConfig,
    InsufficientDataError,
    build_spot_index,
)
from core.ingestion.protocols import Snapshot, SpotIndexPoint, ensure_utc

#: Heure du fix quotidien canonique (UTC) — analogue au fix 00:30 de GPU Markets.
DEFAULT_FIX_TIME = dt.time(0, 30)

#: Colonnes auditables exposées par :meth:`IndexSeries.to_frame`.
_FRAME_COLUMNS = [
    "as_of",
    "gpu_model",
    "price_usd_per_hour",
    "n_sources",
    "method",
    "oldest_obs_at",
]


def daily_fix_grid(
    start: dt.datetime, end: dt.datetime, fix_time: dt.time = DEFAULT_FIX_TIME
) -> list[dt.datetime]:
    """Liste les instants de fix quotidien (``fix_time`` UTC) dans ``[start, end]``.

    Parameters
    ----------
    start, end
        Bornes UTC tz-aware (un datetime naïf est rejeté — intégrité point-in-time).
    fix_time
        Heure du fix dans la journée (défaut 00:30 UTC).

    Returns
    -------
    list[datetime.datetime]
        Un instant par jour calendaire tombant dans ``[start, end]`` (bornes incluses).
    """
    start, end = ensure_utc(start), ensure_utc(end)
    grid: list[dt.datetime] = []
    day = start.date()
    while day <= end.date():
        candidate = dt.datetime.combine(day, fix_time, tzinfo=dt.timezone.utc)
        if start <= candidate <= end:
            grid.append(candidate)
        day += dt.timedelta(days=1)
    return grid


def observed_fix_grid(
    snapshots: Sequence[Snapshot], *, gpu_model: str | None = None
) -> list[dt.datetime]:
    """Cadence **démo** : instants de snapshot observés distincts, triés.

    Sert à rendre une courbe sur l'historique réel maigre (cadence fine, étiquetée démo),
    là où le fix quotidien canonique ne produirait qu'un point. Optionnellement filtré par
    ``gpu_model``.
    """
    times = {s.snapshotted_at for s in snapshots if gpu_model is None or s.gpu_model == gpu_model}
    return sorted(times)


@dataclass(frozen=True)
class IndexSeries:
    """Série d'indice canonique pour un modèle GPU + les fix sautés (données creuses).

    ``points`` est la série calculée (un :class:`SpotIndexPoint` auditable par fix) ;
    ``skipped`` liste les ``as_of`` sans venue fraîche — l'historique maigre est explicite,
    jamais comblé par carry-forward.
    """

    gpu_model: str
    points: list[SpotIndexPoint]
    skipped: list[dt.datetime]

    def to_frame(self) -> pd.DataFrame:
        """Sérialise ``points`` en DataFrame auditable (colonnes :data:`_FRAME_COLUMNS`)."""
        rows = [
            {
                "as_of": p.as_of,
                "gpu_model": p.gpu_model,
                "price_usd_per_hour": p.price_usd_per_hour,
                "n_sources": p.n_sources,
                "method": p.method,
                "oldest_obs_at": p.oldest_obs_at,
            }
            for p in self.points
        ]
        return pd.DataFrame(rows, columns=_FRAME_COLUMNS)


def build_index_series(
    snapshots: Sequence[Snapshot],
    as_of_grid: Sequence[dt.datetime],
    gpu_model: str,
    *,
    config: IndexConfig = DEFAULT_INDEX_CONFIG,
) -> IndexSeries:
    """Échantillonne l'indice canonique de ``gpu_model`` sur ``as_of_grid``.

    Chaque ``as_of`` produit un fix via ``build_spot_index`` ; un fix sans venue fraîche
    (``InsufficientDataError``) est enregistré dans ``skipped`` plutôt que comblé.

    Parameters
    ----------
    snapshots
        Relevés bruts multi-venues (filtrés par ``build_spot_index``).
    as_of_grid
        Instants de fix (UTC) — typiquement issus de :func:`daily_fix_grid`.
    gpu_model
        Modèle agrégé (ex. ``"H100"``).
    config
        Stratégie d'agrégation (défaut : standard marché).

    Returns
    -------
    IndexSeries
        Points calculés + ``as_of`` sautés (données creuses).
    """
    points: list[SpotIndexPoint] = []
    skipped: list[dt.datetime] = []
    for as_of in as_of_grid:
        try:
            points.append(build_spot_index(snapshots, as_of, gpu_model, config=config))
        except InsufficientDataError:
            skipped.append(ensure_utc(as_of))
    return IndexSeries(gpu_model=gpu_model, points=points, skipped=skipped)
