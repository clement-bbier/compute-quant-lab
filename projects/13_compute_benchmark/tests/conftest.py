"""Shared fixtures for P13 tests (multi-venue index + dispersion).

**Synthetic** data calibrated for known results (same conventions as
P04): no test depends on real cold store files. ``src/`` is made
importable for ``from benchmark... import ...``.
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pytest

from core.ingestion.protocols import Snapshot

# Makes the project package `benchmark` (under src/) importable in tests.
_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

#: Reference daily fix (00:30 UTC, analogous to the GPU Markets fix) — day D.
FIX_DAY2 = dt.datetime(2026, 6, 21, 0, 30, tzinfo=dt.timezone.utc)
#: Daily fix for day D-1.
FIX_DAY1 = FIX_DAY2 - dt.timedelta(days=1)


@pytest.fixture
def fix_day1() -> dt.datetime:
    return FIX_DAY1


@pytest.fixture
def fix_day2() -> dt.datetime:
    return FIX_DAY2


@pytest.fixture
def two_day_snapshots() -> list[Snapshot]:
    """H100 scenario across two daily fix windows (two venues).

    Calibrated for known values, default config (20% trimmed mean + 2.5 MAD,
    24 h staleness, on_demand):

    - **fix D-1** (window ]D-2 00:30, D-1 00:30]): vastai 2.00, runpod 2.20 → index 2.10.
    - **fix D**   (window ]D-1 00:30, D   00:30]): vastai 2.10, runpod 2.30 → index 2.20.

    Dispersion at fix D: 2 venues {2.10, 2.30}, index 2.20 → spread 0.20, cheapest vastai.
    """
    h = "H100"
    return [
        # Window of fix D-1 (a few hours before D-1 00:30).
        Snapshot(
            FIX_DAY1 - dt.timedelta(hours=2), "vastai", h, 2.00, availability=100, simulated=False
        ),
        Snapshot(
            FIX_DAY1 - dt.timedelta(hours=2), "runpod", h, 2.20, availability=50, simulated=False
        ),
        # Window of fix D (a few hours before D 00:30).
        Snapshot(
            FIX_DAY2 - dt.timedelta(hours=2), "vastai", h, 2.10, availability=100, simulated=False
        ),
        Snapshot(
            FIX_DAY2 - dt.timedelta(hours=2), "runpod", h, 2.30, availability=50, simulated=False
        ),
    ]
