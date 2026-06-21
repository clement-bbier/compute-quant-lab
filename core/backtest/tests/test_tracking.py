"""Capture de la version DVC pour la reproductibilité (best-effort, jamais bloquant)."""

from __future__ import annotations

from core.backtest.tracking import dvc_version


def test_dvc_version_reports_no_data_when_untracked(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # aucun dvc.lock ici
    assert dvc_version() == "no-dvc-data"


def test_dvc_version_hashes_lockfile_when_present(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "dvc.lock").write_bytes(b"schema: '2.0'\n")
    version = dvc_version()
    assert version != "no-dvc-data"
    assert len(version) == 12  # hash court
