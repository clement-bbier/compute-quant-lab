"""Deterministic fixtures for the ``core.ingestion`` package tests (no network).

Follows the lab's conftest pattern (see ``core/storage/tests``, ``core/features/tests``):
fixtures return data or factories, with no cross-test imports, since a ``tests/``
directory is not a package. No live API is ever contacted.
"""

from __future__ import annotations

import datetime as dt

import pytest

#: Frozen snapshot instant (UTC, tz-aware), shared by the golden cases.
NOW = dt.datetime(2026, 6, 21, 12, 0, tzinfo=dt.timezone.utc)


@pytest.fixture
def now() -> dt.datetime:
    """Frozen snapshot instant (UTC, tz-aware)."""
    return NOW
