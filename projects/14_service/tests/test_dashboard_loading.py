"""Loading behaviour of the dashboard shell: which instant, and which models, it opens on.

Two invariants keep the page renderable against the committed lake, and these tests pin
them: the market is read at the lake's newest instant rather than at wall-clock ``now``
(which would fall outside the 24 h staleness window and yield no fix), and the model picker
offers only models quoted by 2+ venues (a single-venue SKU has nothing to compare).
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import sys
from pathlib import Path

import pytest

from core.ingestion.protocols import Snapshot

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from conftest import FakeSnapshotStore  # noqa: E402


def _load_app_module():
    """Import ``dashboard/app.py`` as a module without executing ``render()``."""
    path = Path(__file__).resolve().parents[1] / "dashboard" / "app.py"
    spec = importlib.util.spec_from_file_location("p14_dashboard_app", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def app():
    return _load_app_module()


def test_fix_instant_is_the_latest_observation(app) -> None:
    """The dashboard reads at the lake's newest instant, not at wall-clock now."""
    latest = dt.datetime(2026, 7, 21, 18, 41, tzinfo=dt.timezone.utc)
    store = FakeSnapshotStore(
        [
            Snapshot(latest - dt.timedelta(hours=3), "runpod", "H100", 2.20, simulated=False),
            Snapshot(latest, "vastai", "H100", 2.00, simulated=False),
        ]
    )
    assert app._fix_instant(store) == latest


def test_fix_instant_never_returns_a_future_instant(app) -> None:
    """Point-in-time: the fix instant is bounded by what the store actually holds."""
    store = FakeSnapshotStore(
        [
            Snapshot(
                dt.datetime(2026, 7, 1, tzinfo=dt.timezone.utc),
                "vastai",
                "H100",
                2.0,
                simulated=False,
            )
        ]
    )
    stored = [s.snapshotted_at for s in store.load()]
    assert app._fix_instant(store) <= max(stored)


def test_fix_instant_falls_back_to_now_on_empty_lake(app) -> None:
    before = dt.datetime.now(tz=dt.timezone.utc)
    instant = app._fix_instant(FakeSnapshotStore([]))
    assert before <= instant <= dt.datetime.now(tz=dt.timezone.utc)


def test_available_models_drops_single_venue_skus(app) -> None:
    """A model quoted by one venue alone cannot be benchmarked cross-venue."""
    store = FakeSnapshotStore(
        [
            Snapshot(
                dt.datetime(2026, 7, 1, tzinfo=dt.timezone.utc),
                "vastai",
                "H100",
                2.0,
                simulated=False,
            ),
            Snapshot(
                dt.datetime(2026, 7, 1, tzinfo=dt.timezone.utc),
                "runpod",
                "H100",
                2.1,
                simulated=False,
            ),
            Snapshot(
                dt.datetime(2026, 7, 1, tzinfo=dt.timezone.utc),
                "cudo",
                "1XB300SXM6262GB",
                9.0,
                simulated=False,
            ),
        ]
    )
    assert app._available_models(store) == ["H100"]


def test_available_models_ranks_by_venue_coverage(app) -> None:
    """Best-covered model first: the page opens on the most comparable market."""
    at = dt.datetime(2026, 7, 1, tzinfo=dt.timezone.utc)
    store = FakeSnapshotStore(
        [
            Snapshot(at, "vastai", "A100", 1.0, simulated=False),
            Snapshot(at, "runpod", "A100", 1.1, simulated=False),
            Snapshot(at, "cudo", "A100", 1.2, simulated=False),
            Snapshot(at, "vastai", "H100", 2.0, simulated=False),
            Snapshot(at, "runpod", "H100", 2.1, simulated=False),
        ]
    )
    assert app._available_models(store) == ["A100", "H100"]


def test_available_models_falls_back_when_lake_is_empty(app) -> None:
    assert app._available_models(FakeSnapshotStore([])) == app._FALLBACK_MODELS
