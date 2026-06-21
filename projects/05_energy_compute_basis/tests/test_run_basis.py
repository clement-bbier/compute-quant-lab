"""Test smoke d'intégration : run_basis loggue un run MLflow et écrit la synthèse."""

from __future__ import annotations

from pathlib import Path

import mlflow


def test_main_logs_mlflow_and_writes_synthesis(tmp_path: Path) -> None:
    """Bout-en-bout hors réseau : basis produit, run MLflow loggué, SYNTHESIS.md écrit."""
    mlflow.set_tracking_uri((tmp_path / "mlruns").as_uri())

    from run_basis import main

    result, dislocations = main(
        results_dir=tmp_path,
        periods=72,
        allow_remote=False,
        experiment="p05_test",
    )

    assert "FR" in result.basis
    assert "FR" in dislocations
    assert (tmp_path / "SYNTHESIS.md").exists()

    runs = mlflow.search_runs(experiment_names=["p05_test"])
    assert len(runs) >= 1
    # Les sources (réel vs synthétique) sont tracées dans les params du run.
    assert runs.iloc[0]["params.energy_source"] == "synthetic"
