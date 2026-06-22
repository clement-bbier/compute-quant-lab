"""Tests du prior PUE region-keyed (Task A2/A3, plan sprint pricing/énergie)."""

from __future__ import annotations

import pytest

from core.pricing.pue_prior import ERCOT_TEXAS_PRIOR, PuePrior


def test_point_estimate_is_mu() -> None:
    p = PuePrior(mu=1.45, sigma=0.15, low=1.2, high=1.8)
    assert p.point_estimate() == pytest.approx(1.45)


def test_sensitivity_bounds_are_support() -> None:
    p = PuePrior(mu=1.45, sigma=0.15, low=1.2, high=1.8)
    assert p.sensitivity_bounds() == (1.2, 1.8)


def test_samples_respect_support_and_physics() -> None:
    p = PuePrior(mu=1.45, sigma=0.15, low=1.2, high=1.8)
    xs = p.sample(10_000, seed=7)
    assert xs.min() >= 1.2
    assert xs.max() <= 1.8
    assert (xs >= 1.0).all()  # PUE >= 1 par définition physique


def test_samples_are_deterministic() -> None:
    p = PuePrior(mu=1.45, sigma=0.15, low=1.2, high=1.8)
    a = p.sample(100, seed=7)
    b = p.sample(100, seed=7)
    assert (a == b).all()  # déterminisme exigé par le labo


def test_low_below_one_rejected() -> None:
    with pytest.raises(ValueError):
        PuePrior(mu=1.05, sigma=0.1, low=0.9, high=1.3)


def test_mu_outside_support_rejected() -> None:
    with pytest.raises(ValueError):
        PuePrior(mu=2.0, sigma=0.1, low=1.2, high=1.8)


def test_texas_prior_matches_l0() -> None:
    assert ERCOT_TEXAS_PRIOR.point_estimate() == pytest.approx(1.45)
    assert ERCOT_TEXAS_PRIOR.sensitivity_bounds() == (1.2, 1.8)
