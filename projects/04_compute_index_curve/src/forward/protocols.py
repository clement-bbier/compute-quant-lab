"""Protocoles injectables de la jambe forward (Strategy + DI).

Deux abstractions interchangeables, dans l'esprit configurable du labo :

- :class:`ForwardCurveModel` — produit une :class:`~forward.models.Curve` à partir d'un
  spot et de paramètres (impl analytique Python, MC Python, MC Rust) ;
- :class:`ForwardCalibrator` — estime les :class:`~forward.models.SchwartzParams` à
  partir d'un historique de log-prix (impl OLS AR(1), demi-vie imposée, …).

Ajouter un modèle/calibrateur = nouvelle implémentation, sans toucher l'orchestration
``build_curve`` (Open/Closed).
"""

from __future__ import annotations

from typing import Protocol, Sequence, runtime_checkable

from forward.models import Curve, SchwartzParams


@runtime_checkable
class ForwardCurveModel(Protocol):
    """Modèle de génération de courbe forward (toujours ``simulated=True`` ici)."""

    @property
    def name(self) -> str:
        """Identifiant du modèle (tracé dans ``Curve.model_name`` et MLflow)."""
        ...

    def simulate(
        self,
        spot: float,
        params: SchwartzParams,
        maturities_days: Sequence[float],
    ) -> Curve:
        """Construit la courbe forward aux échéances ``maturities_days`` (en jours)."""
        ...


@runtime_checkable
class ForwardCalibrator(Protocol):
    """Estimation des paramètres de Schwartz à partir d'un historique de log-prix."""

    @property
    def name(self) -> str:
        """Identifiant du calibrateur (tracé dans MLflow)."""
        ...

    def calibrate(self, log_prices: Sequence[float], dt_days: float) -> SchwartzParams:
        """Calibre ``kappa, theta, sigma`` sur ``log_prices`` espacés de ``dt_days`` jours."""
        ...
