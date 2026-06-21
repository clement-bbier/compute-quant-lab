"""Fixtures partagées des tests P04 (indice spot + courbe forward)."""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pytest

from core.ingestion.protocols import Snapshot

# Rend le paquet projet `forward` (sous src/) importable dans les tests.
_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# Instant de référence du fix (analogue au fix quotidien 00:30 UTC de GPU Markets).
AS_OF = dt.datetime(2026, 6, 21, 0, 30, tzinfo=dt.timezone.utc)


def _ago(hours: float) -> dt.datetime:
    """Horodatage UTC situé ``hours`` heures avant ``AS_OF``."""
    return AS_OF - dt.timedelta(hours=hours)


@pytest.fixture
def as_of() -> dt.datetime:
    return AS_OF


@pytest.fixture
def index_snapshots() -> list[Snapshot]:
    """Jeu H100 on_demand calibré pour un résultat connu.

    4 venues valides (vastai/runpod/lambda/coreweave), plus des pièges qui doivent
    tous être écartés : un outlier (rejeté par MAD), un relevé périmé (> 24 h),
    un hyperscaler (exclu de l'estimateur), un relevé futur (look-ahead) et un autre
    modèle de GPU. Indice attendu (config par défaut) = 2.15 $/GPU·h.
    """
    h = "H100"
    return [
        Snapshot(_ago(1), "vastai", h, 2.00, availability=100),
        Snapshot(_ago(2), "runpod", h, 2.20, availability=50),
        Snapshot(_ago(0.5), "lambda", h, 2.10, availability=200),
        Snapshot(_ago(3), "coreweave", h, 2.30, availability=10),  # plus vieux retenu
        Snapshot(_ago(0.2), "scam", h, 0.05, availability=1),      # outlier -> MAD
        Snapshot(_ago(30), "old", h, 1.50, availability=99),       # périmé > 24 h
        Snapshot(_ago(0.1), "aws", h, 5.00, availability=999),     # hyperscaler exclu
        Snapshot(AS_OF + dt.timedelta(hours=1), "future", h, 9.99),  # look-ahead
        Snapshot(_ago(1), "vastai", "A100", 1.00),                 # autre GPU
    ]
