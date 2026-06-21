"""Fixtures partagées des tests de features point-in-time.

Les helpers sont exposés comme *factories* (fixtures renvoyant un callable) pour
éviter tout import inter-tests fragile (le dossier `tests/` n'est pas un package).
"""

from __future__ import annotations

from typing import Callable

import pandas as pd
import pytest

from core.features.protocols import KNOWLEDGE_TS, VALUE, VALUE_TS

#: Origine commune des séries de test (UTC tz-aware).
_ORIGIN = pd.Timestamp("2025-01-01", tz="UTC")


@pytest.fixture
def day_ts() -> Callable[[int], pd.Timestamp]:
    """Renvoie ``J0 + k jours`` en UTC (J0 = 2025-01-01)."""

    def _day(k: int) -> pd.Timestamp:
        return _ORIGIN + pd.Timedelta(days=k)

    return _day


@pytest.fixture
def make_vintages() -> Callable[[list[tuple[pd.Timestamp, pd.Timestamp, float]]], pd.DataFrame]:
    """Construit un frame vintage depuis des tuples ``(value_ts, knowledge_ts, value)``."""

    def _make(records: list[tuple[pd.Timestamp, pd.Timestamp, float]]) -> pd.DataFrame:
        return pd.DataFrame([{VALUE_TS: v, KNOWLEDGE_TS: k, VALUE: x} for (v, k, x) in records])

    return _make


class _FakeExogenousSource:
    """Source en mémoire (implémente le protocole `ExogenousSource`)."""

    def __init__(self, frames: dict[str, pd.DataFrame]) -> None:
        self._frames = frames

    def names(self) -> list[str]:
        return list(self._frames)

    def vintages(self, name: str) -> pd.DataFrame:
        return self._frames[name]


@pytest.fixture
def fake_source() -> Callable[[dict[str, pd.DataFrame]], _FakeExogenousSource]:
    """Renvoie une factory de source exogène à partir de frames vintage."""
    return _FakeExogenousSource
