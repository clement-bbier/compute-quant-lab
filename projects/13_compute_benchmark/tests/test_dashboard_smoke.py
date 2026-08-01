"""Smoke test for the Streamlit dashboard: does the script actually render?

Import-only coverage would miss errors that only surface once Streamlit executes the
script body (unregistered widget, bad DataFrame shape, etc.). ``AppTest`` runs the real
``dashboard/app.py`` end to end and reports the first uncaught exception, if any.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from streamlit.testing.v1 import AppTest

import core.utils.config as config

_APP_PATH = str(Path(__file__).resolve().parents[1] / "dashboard" / "app.py")


def test_dashboard_renders_on_empty_cold_store(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(config, "SNAPSHOTS_DIR", tmp_path)

    at = AppTest.from_file(_APP_PATH)
    at.run(timeout=30)

    assert not at.exception
    assert any("empty" in w.value.lower() for w in at.warning)


def test_dashboard_renders_with_snapshots(monkeypatch, two_day_snapshots) -> None:
    from core.storage import ParquetSnapshotStore

    root = Path(tempfile.mkdtemp())
    ParquetSnapshotStore(root).append(two_day_snapshots)
    monkeypatch.setattr(config, "SNAPSHOTS_DIR", root)

    at = AppTest.from_file(_APP_PATH)
    at.run(timeout=30)

    assert not at.exception
