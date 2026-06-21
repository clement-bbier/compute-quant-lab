"""Fixtures partagées des tests P05 (basis énergie ↔ compute inter-régions).

Toutes les séries sont déterministes et à valeurs connues (calculables à la main),
index UTC tz-aware. Aucun accès réseau : l'I/O réelle vit dans ``src/data.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

# Rend les modules projet (sous src/) importables dans les tests : `from basis import ...`.
_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


@pytest.fixture
def utc_index() -> pd.DatetimeIndex:
    """Grille horaire UTC tz-aware (4 points) — bord gauche 2026-01-01."""
    return pd.date_range("2026-01-01", periods=4, freq="h", tz="UTC")


@pytest.fixture
def energy_two_regions(utc_index: pd.DatetimeIndex) -> pd.DataFrame:
    """Prix élec €/MWh pour FR et DE : FR tantôt sous, tantôt au-dessus de DE."""
    return pd.DataFrame(
        {
            "FR": [100.0, 120.0, 80.0, 110.0],
            "DE": [90.0, 130.0, 95.0, 100.0],
        },
        index=utc_index,
    )


@pytest.fixture
def compute_global(utc_index: pd.DatetimeIndex) -> pd.DataFrame:
    """Indice compute GLOBAL ($/GPU·h) : une seule colonne, identique pour toutes les régions."""
    return pd.DataFrame({"H100": [2.00, 2.00, 2.00, 2.00]}, index=utc_index)
