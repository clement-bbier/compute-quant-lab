"""Fixtures des tests WS — couche produit ``service_product``.

Doubles en mémoire (aucune I/O Parquet) et jeu de snapshots calibré pour des
résultats connus, repris des conventions P04 (indice par défaut = 2.15 $/GPU·h).
"""

from __future__ import annotations

import datetime as dt
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import pytest

from core.ingestion.protocols import Snapshot

# Rend les modules produit (sous src/) importables dans les tests (convention labo).
_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

#: Instant de référence du fix (fix quotidien 00:30 UTC, cohérent avec P04).
AS_OF = dt.datetime(2026, 6, 21, 0, 30, tzinfo=dt.timezone.utc)


def ago(hours: float) -> dt.datetime:
    """Horodatage UTC situé ``hours`` heures avant :data:`AS_OF`."""
    return AS_OF - dt.timedelta(hours=hours)


@dataclass
class FakeSnapshotStore:
    """Double de test du Protocol ``SnapshotStore`` (en mémoire, sans Parquet)."""

    rows: list[Snapshot] = field(default_factory=list)

    def append(self, rows: Iterable[Snapshot]) -> Path:
        self.rows.extend(rows)
        return Path(".")

    def load(self) -> list[Snapshot]:
        return list(self.rows)


def h100_snapshots() -> list[Snapshot]:
    """Jeu H100 on_demand calibré : indice par défaut = 2.15 $/GPU·h (cf. P04).

    4 venues fraîches valides + pièges à écarter : outlier (rejet MAD), relevé périmé
    (> 24 h), hyperscaler (exclu), relevé futur (look-ahead), autre modèle de GPU.
    Ranking des venues *retenues* : vastai 2.00 < lambda 2.10 < runpod 2.20 < coreweave 2.30.
    """
    h = "H100"
    return [
        Snapshot(ago(1), "vastai", h, 2.00, availability=100),
        Snapshot(ago(2), "runpod", h, 2.20, availability=50),
        Snapshot(ago(0.5), "lambda", h, 2.10, availability=200),
        Snapshot(ago(3), "coreweave", h, 2.30, availability=10),
        Snapshot(ago(0.2), "scam", h, 0.05, availability=1),  # outlier -> rejet MAD
        Snapshot(ago(30), "old", h, 1.50, availability=99),  # périmé > 24 h
        Snapshot(ago(0.1), "aws", h, 5.00, availability=999),  # hyperscaler exclu
        Snapshot(AS_OF + dt.timedelta(hours=1), "future", h, 9.99),  # look-ahead
        Snapshot(ago(1), "vastai", "A100", 1.00),  # autre GPU
    ]


@pytest.fixture
def as_of() -> dt.datetime:
    return AS_OF


@pytest.fixture
def store() -> FakeSnapshotStore:
    return FakeSnapshotStore(h100_snapshots())


@pytest.fixture
def empty_store() -> FakeSnapshotStore:
    return FakeSnapshotStore([])
