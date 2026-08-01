"""Tests for the cointegration toolkit (Engle-Granger, Johansen, half-life, stability).

Known analytical cases: detection on a constructed cointegrated pair, **rejection** on two
independent random walks (anti-spurious), recovery of the OU half-life, and
point-in-time proof of the rolling re-estimation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from cointegration import (
    adf_test,
    engle_granger,
    half_life,
    johansen,
    kpss_test,
    rolling_cointegration,
)


def test_engle_granger_detects_known_cointegration(cointegrated_pair) -> None:
    y, x, beta = cointegrated_pair
    result = engle_granger(y, x)
    assert result.is_cointegrated
    assert result.pvalue < 0.05
    assert abs(result.hedge_ratio - beta) < 0.10  # recovered β ≈ true β


def test_engle_granger_rejects_independent_random_walks(independent_random_walks) -> None:
    y, x = independent_random_walks
    result = engle_granger(y, x)
    assert not result.is_cointegrated
    assert result.pvalue > 0.10


def test_adf_flags_unit_root_and_stationary_series(cointegrated_pair) -> None:
    y, x, _ = cointegrated_pair
    # x is I(1) (random walk) -> ADF does not reject the unit root.
    assert not adf_test(x).is_stationary
    # The cointegration residual is stationary -> ADF rejects the unit root.
    residuals = engle_granger(y, x).residuals
    assert adf_test(residuals).is_stationary


def test_kpss_agrees_on_stationary_residual(cointegrated_pair) -> None:
    y, x, _ = cointegrated_pair
    residuals = engle_granger(y, x).residuals
    # KPSS: null hypothesis = stationarity -> we do not reject it for a stationary residual.
    assert kpss_test(residuals).is_stationary


def test_johansen_finds_one_relation_for_cointegrated_pair(cointegrated_pair) -> None:
    y, x, _ = cointegrated_pair
    frame = pd.concat([y, x], axis=1)
    result = johansen(frame)
    assert result.n_relations >= 1


def test_johansen_finds_no_relation_for_independent_walks(independent_random_walks) -> None:
    y, x = independent_random_walks
    frame = pd.concat([y, x], axis=1)
    result = johansen(frame)
    assert result.n_relations == 0


def test_half_life_recovers_known_ou_half_life(ou_spread_known_half_life) -> None:
    spread, expected_hl = ou_spread_known_half_life
    hl = half_life(spread)
    assert hl > 0.0
    assert abs(hl - expected_hl) / expected_hl < 0.25  # within 25% (finite noise)


def test_rolling_cointegration_is_point_in_time(cointegrated_pair) -> None:
    """The value at instant i must depend ONLY on data ≤ i (no future leakage)."""
    y, x, _ = cointegrated_pair
    window = 200
    rolling = rolling_cointegration(y, x, window=window)
    assert list(rolling.columns) == ["hedge_ratio", "pvalue"]
    # Recompute on the series truncated at i: the last row must match rolling[i].
    i = 400
    truncated = rolling_cointegration(y.iloc[: i + 1], x.iloc[: i + 1], window=window)
    np.testing.assert_allclose(
        truncated.iloc[-1].to_numpy(), rolling.iloc[i].to_numpy(), rtol=1e-12, atol=1e-12
    )
    # The first incomplete windows are NaN (no estimation with < window points).
    assert rolling["hedge_ratio"].iloc[: window - 1].isna().all()
