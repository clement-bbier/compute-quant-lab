"""Forward curve orchestration test: wiring + replayable MLflow logging."""

from __future__ import annotations

import math

import mlflow
import pytest

from forward.build_curve import build_forward_curve, select_forward_model
from forward.calibrators import ImposedHalfLifeCalibrator
from forward.oracle import PythonMonteCarloForward


def test_build_forward_curve_logs_and_returns_simulated(tmp_path, monkeypatch) -> None:
    # MLflow 2026 requires this opt-in for the local file store (lab convention).
    monkeypatch.setenv("MLFLOW_ALLOW_FILE_STORE", "true")
    monkeypatch.setenv("MLFLOW_TRACKING_URI", (tmp_path / "mlruns").as_uri())
    history = [math.log(v) for v in (2.0, 2.1, 1.95, 2.05, 2.0, 1.98)]

    curve = build_forward_curve(
        history,
        spot=2.0,
        maturities_days=[0.0, 30.0, 90.0],
        calibrator=ImposedHalfLifeCalibrator(30.0),
        model=PythonMonteCarloForward(n_paths=20_000, seed=1),
    )

    assert curve.simulated is True
    assert len(curve.points) == 3
    assert curve.prices[0] == pytest.approx(2.0, rel=0.05)  # convergence to spot

    runs = mlflow.search_runs(experiment_names=["compute_forward_curve"])
    assert len(runs) >= 1


def test_select_forward_model_uses_rust_when_built() -> None:
    pytest.importorskip(
        "forward_engine", reason="forward_engine crate not built (run `make kernels`)"
    )
    _, engine = select_forward_model(seed=0, n_paths=1000)
    assert engine == "rust"
