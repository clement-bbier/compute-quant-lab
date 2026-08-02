"""Smoke test for the Streamlit dashboard: does the script actually render?

Import-only coverage would miss errors that only surface once Streamlit executes the
script body. ``AppTest`` runs the real ``dashboard/app.py`` end to end (via ``render()``,
called under its ``if __name__ == "__main__"`` guard) and reports the first uncaught
exception, if any.
"""

from __future__ import annotations

import datetime as dt
import tempfile
from pathlib import Path

from streamlit.testing.v1 import AppTest

import core.utils.config as config
from core.ingestion.protocols import Snapshot

_APP_PATH = str(Path(__file__).resolve().parents[1] / "dashboard" / "app.py")


def test_dashboard_renders_on_empty_cold_store(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(config, "SNAPSHOTS_DIR", tmp_path)

    at = AppTest.from_file(_APP_PATH)
    at.run(timeout=30)

    assert not at.exception
    assert any("no usable reading" in w.value.lower() for w in at.warning)


def test_dashboard_renders_with_snapshots(monkeypatch) -> None:
    from core.storage import ParquetSnapshotStore

    now = dt.datetime.now(tz=dt.timezone.utc)
    snapshots = [
        Snapshot(
            now - dt.timedelta(hours=1), "vastai", "H100", 2.00, availability=100, simulated=False
        ),
        Snapshot(
            now - dt.timedelta(hours=2), "runpod", "H100", 2.20, availability=50, simulated=False
        ),
    ]
    root = Path(tempfile.mkdtemp())
    ParquetSnapshotStore(root).append(snapshots)
    monkeypatch.setattr(config, "SNAPSHOTS_DIR", root)

    at = AppTest.from_file(_APP_PATH)
    at.run(timeout=30)

    assert not at.exception
