"""Construction d'une série temporelle de l'indice spot compute (consommateur de core).

P03 a besoin d'une **série** de prix spot pour estimer la volatilité, alors que
``core.ingestion.build_spot_index`` produit un fix unique par ``as_of``. Ce module
rejoue le constructeur d'indice sur une grille de fix, en restant strictement
**point-in-time** (chaque fix n'utilise que ``snapshotted_at <= as_of``, garanti par
``build_spot_index``) et en ignorant les instants sans données fraîches (no carry-forward).

Pur consommateur de ``core/`` (lecture seule) : aucune logique d'agrégation dupliquée ici.
"""

from __future__ import annotations

import datetime as dt
from typing import Sequence

import numpy as np

from core.ingestion import (
    DEFAULT_INDEX_CONFIG,
    IndexConfig,
    InsufficientDataError,
    Snapshot,
    build_spot_index,
)


def build_spot_series(
    snapshots: Sequence[Snapshot],
    as_of_grid: Sequence[dt.datetime],
    gpu_model: str,
    *,
    config: IndexConfig = DEFAULT_INDEX_CONFIG,
) -> tuple[list[dt.datetime], np.ndarray]:
    """Série de l'indice spot sur ``as_of_grid`` (instants non résolubles ignorés).

    Parameters
    ----------
    snapshots
        Relevés bruts (toutes sources/modèles confondus).
    as_of_grid
        Grille d'instants de fix (UTC), croissante de préférence.
    gpu_model
        Modèle agrégé (ex. ``"H100"``).
    config
        Config d'agrégation injectable (défaut : standard marché).

    Returns
    -------
    tuple[list[datetime], numpy.ndarray]
        Les instants effectivement résolus et les prix $/GPU·h correspondants. Un
        instant sans venue fraîche (``InsufficientDataError``) est **omis** (pas fabriqué).
    """
    times: list[dt.datetime] = []
    prices: list[float] = []
    for as_of in as_of_grid:
        try:
            point = build_spot_index(snapshots, as_of, gpu_model, config=config)
        except InsufficientDataError:
            continue
        times.append(point.as_of)
        prices.append(point.price_usd_per_hour)
    return times, np.asarray(prices, dtype=float)
