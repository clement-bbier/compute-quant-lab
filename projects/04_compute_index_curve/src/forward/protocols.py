"""Injectable protocols for the forward leg (Strategy + DI).

Two interchangeable abstractions, in the lab's configurable spirit:

- :class:`ForwardCurveModel` — produces a :class:`~forward.models.Curve` from a
  spot and parameters (Python analytical impl, Python MC, Rust MC);
- :class:`ForwardCalibrator` — estimates the :class:`~forward.models.SchwartzParams` from
  a log-price history (OLS AR(1) impl, imposed half-life, …).

Adding a model/calibrator = new implementation, without touching the ``build_curve``
orchestration (Open/Closed).
"""

from __future__ import annotations

from typing import Protocol, Sequence, runtime_checkable

from forward.models import Curve, SchwartzParams


@runtime_checkable
class ForwardCurveModel(Protocol):
    """Forward curve generation model (always ``simulated=True`` here)."""

    @property
    def name(self) -> str:
        """Model identifier (tracked in ``Curve.model_name`` and MLflow)."""
        ...

    def simulate(
        self,
        spot: float,
        params: SchwartzParams,
        maturities_days: Sequence[float],
    ) -> Curve:
        """Builds the forward curve at the ``maturities_days`` maturities (in days)."""
        ...


@runtime_checkable
class ForwardCalibrator(Protocol):
    """Estimation of Schwartz parameters from a log-price history."""

    @property
    def name(self) -> str:
        """Calibrator identifier (tracked in MLflow)."""
        ...

    def calibrate(self, log_prices: Sequence[float], dt_days: float) -> SchwartzParams:
        """Calibrates ``kappa, theta, sigma`` on ``log_prices`` spaced ``dt_days`` days apart."""
        ...
