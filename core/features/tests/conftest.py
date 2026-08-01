"""Shared fixtures of the point-in-time feature tests.

The helpers are exposed as *factories* (fixtures returning a callable) to avoid any
fragile inter-test import (the `tests/` folder is not a package).
"""

from __future__ import annotations

from typing import Callable

import pandas as pd
import pytest

from core.features.protocols import KNOWLEDGE_TS, VALUE, VALUE_TS

#: Common origin of the test series (UTC tz-aware).
_ORIGIN = pd.Timestamp("2025-01-01", tz="UTC")


@pytest.fixture
def day_ts() -> Callable[[int], pd.Timestamp]:
    """Return ``D0 + k days`` in UTC (D0 = 2025-01-01)."""

    def _day(k: int) -> pd.Timestamp:
        return _ORIGIN + pd.Timedelta(days=k)

    return _day


@pytest.fixture
def make_vintages() -> Callable[[list[tuple[pd.Timestamp, pd.Timestamp, float]]], pd.DataFrame]:
    """Build a vintage frame from ``(value_ts, knowledge_ts, value)`` tuples."""

    def _make(records: list[tuple[pd.Timestamp, pd.Timestamp, float]]) -> pd.DataFrame:
        return pd.DataFrame([{VALUE_TS: v, KNOWLEDGE_TS: k, VALUE: x} for (v, k, x) in records])

    return _make


class _FakeExogenousSource:
    """In-memory source (implements the `ExogenousSource` protocol)."""

    def __init__(self, frames: dict[str, pd.DataFrame]) -> None:
        self._frames = frames

    def names(self) -> list[str]:
        return list(self._frames)

    def vintages(self, name: str) -> pd.DataFrame:
        return self._frames[name]


@pytest.fixture
def fake_source() -> Callable[[dict[str, pd.DataFrame]], _FakeExogenousSource]:
    """Return an exogenous source factory built from vintage frames."""
    return _FakeExogenousSource
