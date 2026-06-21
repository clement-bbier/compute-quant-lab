"""Orchestration de la courbe forward SIMULÉE : calibration → simulation → MLflow.

Enchaîne un :class:`~forward.protocols.ForwardCalibrator` (estimation κ, θ, σ sur
l'historique du spot) puis un :class:`~forward.protocols.ForwardCurveModel` (simulation),
et **logue le run dans MLflow** (modèle, moteur, calibrateur, seed, n_paths, params + SHA
git via :func:`core.utils.tracking.run`) pour une rejouabilité totale.

Le moteur est sélectionné par injection : Rust si la crate ``forward_engine`` est buildée,
sinon repli MC Python — l'identité du moteur est tracée (``engine``).
"""

from __future__ import annotations

import logging
from typing import Sequence

import mlflow

from core.utils import tracking
from forward.calibrators import ImposedHalfLifeCalibrator, OlsAr1Calibrator
from forward.models import Curve
from forward.oracle import PythonMonteCarloForward
from forward.protocols import ForwardCalibrator, ForwardCurveModel

logger = logging.getLogger(__name__)

#: Calibrateur par défaut : OLS AR(1) (standard Schwartz) avec repli demi-vie robuste.
DEFAULT_CALIBRATOR: ForwardCalibrator = OlsAr1Calibrator(
    fallback=ImposedHalfLifeCalibrator(half_life_days=30.0)
)


def select_forward_model(seed: int = 0, n_paths: int = 100_000) -> tuple[ForwardCurveModel, str]:
    """Choisit le moteur de simulation : Rust si dispo, sinon MC Python (repli)."""
    try:
        import forward_engine  # noqa: F401  (présence = crate buildée)

        from forward.engine import RustMonteCarloForward

        return RustMonteCarloForward(n_paths=n_paths, seed=seed), "rust"
    except ImportError:
        logger.warning("Crate forward_engine indisponible : repli Monte-Carlo Python.")
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
    """Calibre, simule, logue et renvoie la courbe forward SIMULÉE.

    Parameters
    ----------
    spot_log_history
        Historique des log-prix spot (issu de l'indice) pour la calibration.
    spot
        Spot courant qui sème la courbe.
    maturities_days
        Échéances à pricer (jours).
    calibrator, model
        Stratégies injectables. ``model=None`` sélectionne Rust/Python automatiquement.
    dt_days
        Pas temporel de l'historique (jours).
    experiment
        Nom de l'expérience MLflow.

    Returns
    -------
    Curve
        Courbe ``simulated=True``, déjà loggée dans MLflow.
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
        "Courbe forward SIMULÉE : moteur=%s, calibrateur=%s, %d échéances.",
        engine,
        calibrator.name,
        len(curve.points),
    )
    return curve
