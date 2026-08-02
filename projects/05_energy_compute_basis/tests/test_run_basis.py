"""Integration smoke test: run_basis logs an MLflow run and writes the synthesis."""

from __future__ import annotations

from pathlib import Path

import mlflow
from core.storage.energy_store import EnergyColdStore


def test_main_logs_mlflow_and_writes_synthesis(tmp_path: Path) -> None:
    """Offline end-to-end (empty cold store + allow_remote=False): synthetic fallback,
    MLflow run logged, SYNTHESIS.md written."""
    mlflow.set_tracking_uri((tmp_path / "mlruns").as_uri())

    from run_basis import main

    empty_store = EnergyColdStore(tmp_path / "energy_store")
    result, dislocations = main(
        results_dir=tmp_path,
        periods=72,
        allow_remote=False,
        experiment="p05_test",
        energy_store=empty_store,
    )

    assert "FR" in result.basis
    assert "FR" in dislocations
    assert (tmp_path / "SYNTHESIS.md").exists()

    runs = mlflow.search_runs(experiment_names=["p05_test"])
    assert len(runs) >= 1
    # Sources (real vs synthetic) are tracked in the run's params.
    assert runs.iloc[0]["params.energy_source"] == "synthetic"
