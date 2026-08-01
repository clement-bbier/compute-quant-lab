"""Tests of the volatility estimators (rolling realized + EWMA).

Two key requirements for the PoC tier:
- analytical accuracy on a series with **known vol** (alternating ±a returns);
- **anti look-ahead**: vol at instant t depends only on index returns ≤ t
  (invariance under series truncation).
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from conftest import KNOWN_RETURN_AMPLITUDE, annualized

from vol import EwmaVol, RealizedVol, VolEstimator, log_returns


def test_log_returns_basic() -> None:
    prices = np.array([2.0, 2.0 * math.e, 2.0])
    r = log_returns(prices)
    assert r.shape == (2,)
    assert r[0] == pytest.approx(1.0)
    assert r[1] == pytest.approx(-1.0)


def test_realized_vol_recovers_known_vol(alternating_returns: np.ndarray) -> None:
    window = 10
    est = RealizedVol(window=window, periods_per_year=365.0)
    vol = est.estimate(alternating_returns)
    # Alternating ±a window (even length): std ddof=1 = a*sqrt(w/(w-1)).
    expected = annualized(KNOWN_RETURN_AMPLITUDE * math.sqrt(window / (window - 1)))
    assert vol[-1] == pytest.approx(expected, rel=1e-9)


def test_realized_vol_warmup_is_nan(alternating_returns: np.ndarray) -> None:
    window = 10
    vol = RealizedVol(window=window, periods_per_year=365.0).estimate(alternating_returns)
    assert np.isnan(vol[: window - 1]).all()
    assert not np.isnan(vol[window - 1 :]).any()


def test_ewma_vol_converges_to_known_vol(alternating_returns: np.ndarray) -> None:
    est = EwmaVol(lam=0.94, periods_per_year=365.0)
    vol = est.estimate(alternating_returns)
    # constant r² = a² -> EWMA variance -> a² ; annualized vol -> a*sqrt(ppy).
    expected = annualized(KNOWN_RETURN_AMPLITUDE)
    assert vol[-1] == pytest.approx(expected, rel=1e-6)


@pytest.mark.parametrize(
    "est",
    [RealizedVol(window=10), EwmaVol(lam=0.94)],
    ids=["realized", "ewma"],
)
def test_vol_is_causal_under_truncation(est: VolEstimator, alternating_returns: np.ndarray) -> None:
    """Anti look-ahead: vol[t] identical on the full series and on series[:t+1]."""
    full = est.estimate(alternating_returns)
    for t in (15, 40, 90):
        truncated = est.estimate(alternating_returns[: t + 1])
        a, b = full[t], truncated[t]
        assert (np.isnan(a) and np.isnan(b)) or a == pytest.approx(b, rel=1e-12)


def test_estimators_satisfy_protocol() -> None:
    assert isinstance(RealizedVol(window=10), VolEstimator)
    assert isinstance(EwmaVol(lam=0.94), VolEstimator)
    assert RealizedVol(window=10).name == "realized10"
    assert EwmaVol(lam=0.94).name == "ewma0.94"
