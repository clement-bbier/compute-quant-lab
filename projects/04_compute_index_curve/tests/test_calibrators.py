"""Tests des calibrateurs de paramètres de Schwartz (Strategy interchangeable).

Le test fort : générer une série OU de paramètres connus puis vérifier que l'OLS AR(1)
les recouvre. On teste aussi le repli quand la série n'a pas de mean-reversion.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from forward.calibrators import (
    CalibrationError,
    ImposedHalfLifeCalibrator,
    OlsAr1Calibrator,
)


def _simulate_ou(kappa: float, theta: float, sigma: float, dt: float, n: int, seed: int) -> np.ndarray:
    """Série de log-prix OU (transition exacte) de paramètres connus."""
    rng = np.random.default_rng(seed)
    ln_theta = math.log(theta)
    decay = math.exp(-kappa * dt)
    sd = math.sqrt((sigma**2 / (2.0 * kappa)) * (1.0 - math.exp(-2.0 * kappa * dt)))
    x = np.empty(n)
    x[0] = ln_theta
    for i in range(1, n):
        x[i] = decay * x[i - 1] + (1.0 - decay) * ln_theta + sd * rng.standard_normal()
    return x


def test_ols_recovers_known_parameters() -> None:
    x = _simulate_ou(kappa=0.1, theta=2.0, sigma=0.3, dt=1.0, n=6000, seed=0)
    p = OlsAr1Calibrator().calibrate(x, dt_days=1.0)
    assert p.kappa == pytest.approx(0.1, rel=0.25)
    assert p.theta == pytest.approx(2.0, rel=0.10)
    assert p.sigma == pytest.approx(0.3, rel=0.15)


def test_ols_uses_fallback_when_no_mean_reversion() -> None:
    x = math.log(2.0) * (1.5 ** np.arange(15))  # série explosive -> b=1.5 (pas de reversion)
    fallback = ImposedHalfLifeCalibrator(half_life_days=30.0)
    p = OlsAr1Calibrator(fallback=fallback).calibrate(x, dt_days=1.0)
    assert p.kappa == pytest.approx(math.log(2) / 30.0)  # repli déclenché


def test_ols_raises_without_fallback_on_no_mean_reversion() -> None:
    x = math.log(2.0) * (1.5 ** np.arange(15))
    with pytest.raises(CalibrationError):
        OlsAr1Calibrator().calibrate(x, dt_days=1.0)


def test_halflife_calibrator() -> None:
    x = np.array([math.log(2.0), math.log(2.1), math.log(1.9), math.log(2.0)])
    p = ImposedHalfLifeCalibrator(half_life_days=30.0).calibrate(x, dt_days=1.0)
    assert p.kappa == pytest.approx(math.log(2) / 30.0)
    assert p.theta == pytest.approx(math.exp(float(x.mean())))
    assert p.sigma > 0


def test_calibrator_names() -> None:
    assert OlsAr1Calibrator().name == "ols_ar1"
    assert ImposedHalfLifeCalibrator(30.0).name == "halflife30"
