"""Fixtures partagées des tests P13 (indice multi-venues + dispersion).

Données **synthétiques** calibrées pour des résultats connus (mêmes conventions que
P04) : aucun test ne dépend des fichiers réels du cold store. ``src/`` est rendu
importable pour ``from benchmark... import ...``.
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pytest

from core.ingestion.protocols import Snapshot

# Rend le paquet projet `benchmark` (sous src/) importable dans les tests.
_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

#: Fix quotidien de référence (00:30 UTC, analogue au fix GPU Markets) — jour J.
FIX_DAY2 = dt.datetime(2026, 6, 21, 0, 30, tzinfo=dt.timezone.utc)
#: Fix quotidien du jour J-1.
FIX_DAY1 = FIX_DAY2 - dt.timedelta(days=1)


@pytest.fixture
def fix_day1() -> dt.datetime:
    return FIX_DAY1


@pytest.fixture
def fix_day2() -> dt.datetime:
    return FIX_DAY2


@pytest.fixture
def two_day_snapshots() -> list[Snapshot]:
    """Scénario H100 sur deux fenêtres de fix quotidien (deux venues).

    Calibré pour des valeurs connues, config par défaut (trimmed-mean 20 % + 2.5 MAD,
    staleness 24 h, on_demand) :

    - **fix J-1** (fenêtre ]J-2 00:30, J-1 00:30]) : vastai 2.00, runpod 2.20 → indice 2.10.
    - **fix J**   (fenêtre ]J-1 00:30, J   00:30]) : vastai 2.10, runpod 2.30 → indice 2.20.

    Dispersion au fix J : 2 venues {2.10, 2.30}, indice 2.20 → spread 0.20, cheapest vastai.
    """
    h = "H100"
    return [
        # Fenêtre du fix J-1 (qq heures avant J-1 00:30).
        Snapshot(FIX_DAY1 - dt.timedelta(hours=2), "vastai", h, 2.00, availability=100),
        Snapshot(FIX_DAY1 - dt.timedelta(hours=2), "runpod", h, 2.20, availability=50),
        # Fenêtre du fix J (qq heures avant J 00:30).
        Snapshot(FIX_DAY2 - dt.timedelta(hours=2), "vastai", h, 2.10, availability=100),
        Snapshot(FIX_DAY2 - dt.timedelta(hours=2), "runpod", h, 2.30, availability=50),
    ]
