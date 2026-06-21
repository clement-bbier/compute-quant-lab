"""Calibrateurs des paramètres de Schwartz (κ, θ, σ) — stratégies interchangeables.

- :class:`OlsAr1Calibrator` (défaut) : régression AR(1) du log-prix (standard Schwartz
  1997). Robuste à l'absence de mean-reversion via un *repli* configurable.
- :class:`ImposedHalfLifeCalibrator` : demi-vie imposée + θ/σ d'échantillon ; stable même
  sur un historique court (le cas du spot compute, fraîchement accumulé).

Le modèle discret exact donne, avec ``b = e^{-κΔ}`` :
``κ = -ln(b)/Δ`` · ``θ = exp(a/(1-b))`` · ``σ = std(résidus)·sqrt(-2 ln b /(Δ(1-b²)))``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

import numpy as np

from forward.models import SchwartzParams
from forward.protocols import ForwardCalibrator


class CalibrationError(ValueError):
    """Levée quand la calibration échoue (données insuffisantes, pas de mean-reversion)."""


@dataclass(frozen=True)
class ImposedHalfLifeCalibrator:
    """κ fixé par une demi-vie ; θ et σ estimés sur l'échantillon (robuste, peu de points).

    Parameters
    ----------
    half_life_days
        Demi-vie de retour à la moyenne (jours) ; ``κ = ln 2 / half_life``.
    """

    half_life_days: float = 30.0

    @property
    def name(self) -> str:
        return f"halflife{int(round(self.half_life_days))}"

    def calibrate(self, log_prices: Sequence[float], dt_days: float) -> SchwartzParams:
        x = np.asarray(log_prices, dtype=float)
        if x.size < 2:
            raise CalibrationError("Au moins 2 points requis pour la calibration.")
        kappa = math.log(2.0) / self.half_life_days
        theta = math.exp(float(x.mean()))
        sigma = float(np.std(np.diff(x), ddof=1)) / math.sqrt(dt_days)
        return SchwartzParams(kappa=kappa, theta=theta, sigma=sigma)


@dataclass(frozen=True)
class OlsAr1Calibrator:
    """Calibration OLS AR(1) (standard Schwartz). Repli si la série n'a pas de reversion.

    Parameters
    ----------
    fallback
        Calibrateur de secours utilisé quand la pente ``b`` sort de ``(0, 1)`` (κ non
        positif). Si ``None``, une :class:`CalibrationError` est levée.
    """

    fallback: ForwardCalibrator | None = None

    @property
    def name(self) -> str:
        return "ols_ar1"

    def calibrate(self, log_prices: Sequence[float], dt_days: float) -> SchwartzParams:
        x = np.asarray(log_prices, dtype=float)
        if x.size < 3:
            raise CalibrationError("Au moins 3 points requis pour l'OLS AR(1).")

        x_t, x_next = x[:-1], x[1:]
        slope, intercept = np.polyfit(x_t, x_next, 1)
        b, a = float(slope), float(intercept)

        if not (0.0 < b < 1.0):
            if self.fallback is not None:
                return self.fallback.calibrate(log_prices, dt_days)
            raise CalibrationError(
                f"Pas de mean-reversion exploitable (b={b:.4f} hors (0,1)) : κ non positif."
            )

        kappa = -math.log(b) / dt_days
        theta = math.exp(a / (1.0 - b))
        residuals = x_next - (a + b * x_t)
        resid_std = float(np.std(residuals, ddof=2))
        sigma = resid_std * math.sqrt(-2.0 * math.log(b) / (dt_days * (1.0 - b**2)))
        return SchwartzParams(kappa=kappa, theta=theta, sigma=sigma)
