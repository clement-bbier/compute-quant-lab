"""Fixtures déterministes des tests du cold store (zéro réseau).

Les helpers sont exposés comme *factories* (fixtures renvoyant un callable) — même
patron que ``core/features/tests`` — pour garder des tests lisibles sans import
inter-tests fragile (le dossier ``tests/`` n'est pas un package).
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Sequence

import pandas as pd
import pytest

from core.storage import ParquetPriceStore
from core.storage.schema import (
    AVAILABILITY,
    COLUMNS,
    GPU_MODEL,
    LEASE_TYPE,
    PRICE,
    SNAPSHOTTED_AT,
    SOURCE,
)

#: Origine commune des séries de test (UTC tz-aware).
_ORIGIN = pd.Timestamp("2025-01-01", tz="UTC")

#: Un relevé de test : (heure depuis J0, source, modèle, prix, dispo[, type de bail]).
Record = tuple


@pytest.fixture
def at() -> Callable[[int], pd.Timestamp]:
    """Renvoie ``J0 + h heures`` en UTC (J0 = 2025-01-01)."""

    def _at(hours: int) -> pd.Timestamp:
        return _ORIGIN + pd.Timedelta(hours=hours)

    return _at


@pytest.fixture
def make_frame(at: Callable[[int], pd.Timestamp]) -> Callable[[Sequence[Record]], pd.DataFrame]:
    """Construit un frame canonique typé depuis des tuples ``(h, source, modèle, prix, dispo[, bail])``."""

    def _make(records: Sequence[Record]) -> pd.DataFrame:
        rows = []
        for r in records:
            hour, source, model, price, avail = r[0], r[1], r[2], r[3], r[4]
            lease = r[5] if len(r) > 5 else "on_demand"
            rows.append(
                {
                    SNAPSHOTTED_AT: at(hour),
                    SOURCE: source,
                    GPU_MODEL: model,
                    LEASE_TYPE: lease,
                    PRICE: float(price),
                    AVAILABILITY: int(avail),
                }
            )
        return pd.DataFrame(rows, columns=COLUMNS)

    return _make


@pytest.fixture
def store(tmp_path: Path) -> ParquetPriceStore:
    """Un ``ParquetPriceStore`` vide isolé dans le tmp_path du test."""
    return ParquetPriceStore(tmp_path / "snapshots")
