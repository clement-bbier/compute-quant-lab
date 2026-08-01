"""Deterministic fixtures for the cold store tests (zero network).

The helpers are exposed as *factories* (fixtures returning a callable) — same pattern as
``core/features/tests`` — to keep tests readable without fragile inter-test imports (the
``tests/`` folder is not a package).
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

#: Common origin of the test series (UTC tz-aware).
_ORIGIN = pd.Timestamp("2025-01-01", tz="UTC")

#: A test reading: (hours since D0, source, model, price, availability[, lease type]).
Record = tuple


@pytest.fixture
def at() -> Callable[[int], pd.Timestamp]:
    """Return ``D0 + h hours`` in UTC (D0 = 2025-01-01)."""

    def _at(hours: int) -> pd.Timestamp:
        return _ORIGIN + pd.Timedelta(hours=hours)

    return _at


@pytest.fixture
def make_frame(at: Callable[[int], pd.Timestamp]) -> Callable[[Sequence[Record]], pd.DataFrame]:
    """Build a typed canonical frame from ``(h, source, model, price, avail[, lease])`` tuples."""

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
    """An empty ``ParquetPriceStore`` isolated in the test's tmp_path."""
    return ParquetPriceStore(tmp_path / "snapshots")
