"""Schwartz parameter calibrators (κ, θ, σ) — interchangeable strategies.

- :class:`OlsAr1Calibrator` (default): AR(1) regression on the log-price (standard Schwartz
  1997). Robust to the absence of mean-reversion via a configurable *fallback*.
- :class:`ImposedHalfLifeCalibrator`: imposed half-life + sample θ/σ; stable even
  on a short history (the case of freshly accumulated compute spot).

The exact discrete model gives, with ``b = e^{-κΔ}``:
``κ = -ln(b)/Δ`` · ``θ = exp(a/(1-b))`` · ``σ = std(residuals)·sqrt(-2 ln b /(Δ(1-b²)))``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

import numpy as np

from forward.models import SchwartzParams
from forward.protocols import ForwardCalibrator


class CalibrationError(ValueError):
    """Raised when calibration fails (insufficient data, no mean-reversion)."""


@dataclass(frozen=True)
class ImposedHalfLifeCalibrator:
    """κ fixed by a half-life; θ and σ estimated on the sample (robust, few points).

    Parameters
    ----------
    half_life_days
        Mean-reversion half-life (days); ``κ = ln 2 / half_life``.
    """

    half_life_days: float = 30.0

    @property
    def name(self) -> str:
        return f"halflife{int(round(self.half_life_days))}"

    def calibrate(self, log_prices: Sequence[float], dt_days: float) -> SchwartzParams:
        x = np.asarray(log_prices, dtype=float)
        if x.size < 2:
            raise CalibrationError("At least 2 points are required for calibration.")
        kappa = math.log(2.0) / self.half_life_days
        theta = math.exp(float(x.mean()))
        sigma = float(np.std(np.diff(x), ddof=1)) / math.sqrt(dt_days)
        return SchwartzParams(kappa=kappa, theta=theta, sigma=sigma)


@dataclass(frozen=True)
class OlsAr1Calibrator:
    """OLS AR(1) calibration (standard Schwartz). Falls back if the series has no reversion.

    Parameters
    ----------
    fallback
        Fallback calibrator used when the slope ``b`` falls outside ``(0, 1)`` (non-
        positive κ). If ``None``, a :class:`CalibrationError` is raised.
    """

    fallback: ForwardCalibrator | None = None

    @property
    def name(self) -> str:
        return "ols_ar1"

    def calibrate(self, log_prices: Sequence[float], dt_days: float) -> SchwartzParams:
        x = np.asarray(log_prices, dtype=float)
        if x.size < 3:
            raise CalibrationError("At least 3 points are required for OLS AR(1).")

        x_t, x_next = x[:-1], x[1:]
        slope, intercept = np.polyfit(x_t, x_next, 1)
        b, a = float(slope), float(intercept)

        if not (0.0 < b < 1.0):
            if self.fallback is not None:
                return self.fallback.calibrate(log_prices, dt_days)
            raise CalibrationError(
                f"No usable mean-reversion (b={b:.4f} outside (0,1)): non-positive κ."
            )

        kappa = -math.log(b) / dt_days
        theta = math.exp(a / (1.0 - b))
        residuals = x_next - (a + b * x_t)
        resid_std = float(np.std(residuals, ddof=2))
        sigma = resid_std * math.sqrt(-2.0 * math.log(b) / (dt_days * (1.0 - b**2)))
        return SchwartzParams(kappa=kappa, theta=theta, sigma=sigma)
