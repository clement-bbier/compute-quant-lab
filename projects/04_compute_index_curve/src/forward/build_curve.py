"""Orchestration of the SIMULATED forward curve: calibration → simulation → MLflow.

Chains a :class:`~forward.protocols.ForwardCalibrator` (estimation of κ, θ, σ on
the spot history) then a :class:`~forward.protocols.ForwardCurveModel` (simulation),
and **logs the run to MLflow** (model, engine, calibrator, seed, n_paths, params + git
SHA via :func:`core.utils.tracking.run`) for full reproducibility.

The engine is selected by injection: Rust if the ``forward_engine`` crate is built,
else Python MC fallback — the engine's identity is tracked (``engine``).
"""

from __future__ import annotations

from typing import Sequence

import mlflow

from core.utils import tracking
from core.utils.logging import get_logger
from forward.calibrators import ImposedHalfLifeCalibrator, OlsAr1Calibrator
from forward.models import Curve
from forward.oracle import PythonMonteCarloForward
from forward.protocols import ForwardCalibrator, ForwardCurveModel

logger = get_logger(__name__)

#: Default calibrator: OLS AR(1) (standard Schwartz) with robust half-life fallback.
DEFAULT_CALIBRATOR: ForwardCalibrator = OlsAr1Calibrator(
    fallback=ImposedHalfLifeCalibrator(half_life_days=30.0)
)


def select_forward_model(seed: int = 0, n_paths: int = 100_000) -> tuple[ForwardCurveModel, str]:
    """Chooses the simulation engine: Rust if available, else Python MC (fallback)."""
    try:
        import forward_engine  # noqa: F401  (presence = crate built)

        from forward.engine import RustMonteCarloForward

        return RustMonteCarloForward(n_paths=n_paths, seed=seed), "rust"
    except ImportError:
        logger.warning("forward_engine crate unavailable: falling back to Python Monte-Carlo.")
        return PythonMonteCarloForward(n_paths=n_paths, seed=seed), "python"


def build_forward_curve(
    spot_log_history: Sequence[float],
    spot: float,
    maturities_days: Sequence[float],
    *,
    calibrator: ForwardCalibrator = DEFAULT_CALIBRATOR,
    model: ForwardCurveModel | None = None,
    engine_name: str | None = None,
    dt_days: float = 1.0,
    experiment: str = "compute_forward_curve",
) -> Curve:
    """Calibrates, simulates, logs and returns the SIMULATED forward curve.

    Parameters
    ----------
    spot_log_history
        Log-spot price history (from the index) used for calibration.
    spot
        Current spot that seeds the curve.
    maturities_days
        Maturities to price (days).
    calibrator, model
        Injectable strategies. ``model=None`` auto-selects Rust/Python.
    dt_days
        Time step of the history (days).
    experiment
        MLflow experiment name.

    Returns
    -------
    Curve
        ``simulated=True`` curve, already logged to MLflow.
    """
    params = calibrator.calibrate(spot_log_history, dt_days)
    if model is None:
        model, engine_name = select_forward_model()
    engine = engine_name or model.name

    run_params = {
        "model": model.name,
        "engine": engine,
        "calibrator": calibrator.name,
        "seed": getattr(model, "seed", None),
        "n_paths": getattr(model, "n_paths", None),
        "kappa": params.kappa,
        "theta": params.theta,
        "sigma": params.sigma,
        "dt_days": dt_days,
        "simulated": True,
    }

    with tracking.run(experiment, run_params):
        curve = model.simulate(spot, params, maturities_days)
        mlflow.log_metric("forward_spot", spot)
        mlflow.log_metric("forward_long_run", params.long_run_forward)
        for point in curve.points:
            mlflow.log_metric("forward_price", point.forward_price, step=int(point.maturity_days))

    logger.info(
        "SIMULATED forward curve: engine=%s, calibrator=%s, %d maturities.",
        engine,
        calibrator.name,
        len(curve.points),
    )
    return curve
