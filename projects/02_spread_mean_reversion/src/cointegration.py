"""Energy<->compute cointegration toolkit (foundation of the spread arbitrage).

Two series correlated by chance (spurious correlation) do not license any arbitrage:
we test for a genuine long-term equilibrium relationship before shorting a spread. This module
provides the full protocol from the ``/cointegration-analysis`` skill:

1. Stationarity (ADF + KPSS).
2. Cointegration: Engle-Granger (2 series, hedge ratio + residual) and Johansen (>= 2 series).
3. Mean-reversion half-life (Ornstein-Uhlenbeck).
4. Stability: **point-in-time** re-estimation on a rolling window (anti look-ahead, anti-spurious).

Pure functions (no I/O), immutable and auditable results.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.stattools import adfuller, coint, kpss
from statsmodels.tsa.vector_ar.vecm import coint_johansen

#: Index of the 95% critical threshold in the ``coint_johansen`` tables ([90%, 95%, 99%]).
_CRIT_95 = 1


def _as_array(series: pd.Series | np.ndarray) -> np.ndarray:
    """1-D float64 view of a series/array (working unit for the statistical tests)."""
    return np.asarray(series, dtype=np.float64)


def _as_series(series: pd.Series | np.ndarray) -> pd.Series:
    """Pandas series (preserves the time index if present, otherwise RangeIndex)."""
    return (
        series if isinstance(series, pd.Series) else pd.Series(np.asarray(series, dtype=np.float64))
    )


@dataclass(frozen=True)
class StationarityResult:
    """Result of a stationarity test (ADF or KPSS)."""

    statistic: float
    pvalue: float
    is_stationary: bool


@dataclass(frozen=True)
class EngleGrangerResult:
    """Two-series cointegration: ``y = intercept + hedge_ratio·x + residual``."""

    hedge_ratio: float
    intercept: float
    residuals: pd.Series
    pvalue: float
    is_cointegrated: bool


@dataclass(frozen=True)
class JohansenResult:
    """Johansen test: trace statistics vs. 95% thresholds + cointegration vector."""

    trace_stats: np.ndarray
    trace_crit_95: np.ndarray
    n_relations: int
    cointegration_vector: np.ndarray


def adf_test(series: pd.Series | np.ndarray, *, alpha: float = 0.05) -> StationarityResult:
    """Augmented Dickey-Fuller. Null hypothesis = unit root; stationary if p < ``alpha``."""
    stat, pvalue, *_ = adfuller(_as_array(series), autolag="AIC")
    return StationarityResult(float(stat), float(pvalue), bool(pvalue < alpha))


def kpss_test(series: pd.Series | np.ndarray, *, alpha: float = 0.05) -> StationarityResult:
    """KPSS. Null hypothesis = **stationarity**; stationary if p > ``alpha`` (we do not reject)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # p-value interpolated outside the table: harmless here
        stat, pvalue, *_ = kpss(_as_array(series), regression="c", nlags="auto")
    return StationarityResult(float(stat), float(pvalue), bool(pvalue > alpha))


def engle_granger(
    y: pd.Series | np.ndarray, x: pd.Series | np.ndarray, *, alpha: float = 0.05
) -> EngleGrangerResult:
    """Engle-Granger: OLS ``y ~ x`` for the hedge ratio, cointegration p-value via ``coint``.

    The p-value comes from ``statsmodels.coint`` (MacKinnon critical values) and **not** from a
    raw ADF on the residual: the residual comes from a regression where beta is estimated, which
    over-rejects and manufactures spurious cointegration. The OLS residual remains exposed (the spread to trade).
    """
    y_arr, x_arr = _as_array(y), _as_array(x)
    design = sm.add_constant(x_arr)
    params = sm.OLS(y_arr, design).fit().params
    intercept, hedge_ratio = float(params[0]), float(params[1])
    resid = y_arr - (intercept + hedge_ratio * x_arr)
    pvalue = float(coint(y_arr, x_arr, trend="c", autolag="AIC")[1])
    index = y.index if isinstance(y, pd.Series) else None
    return EngleGrangerResult(
        hedge_ratio=hedge_ratio,
        intercept=intercept,
        residuals=pd.Series(resid, index=index, name="residual"),
        pvalue=pvalue,
        is_cointegrated=bool(pvalue < alpha),
    )


def johansen(frame: pd.DataFrame, *, det_order: int = 0, k_ar_diff: int = 1) -> JohansenResult:
    """Johansen test (trace). ``n_relations`` = number of successive rejections starting from rank 0."""
    result = coint_johansen(np.asarray(frame, dtype=np.float64), det_order, k_ar_diff)
    trace_stats = np.asarray(result.lr1, dtype=np.float64)
    trace_crit_95 = np.asarray(result.cvt[:, _CRIT_95], dtype=np.float64)
    n_relations = int(np.count_nonzero(trace_stats > trace_crit_95))
    return JohansenResult(
        trace_stats=trace_stats,
        trace_crit_95=trace_crit_95,
        n_relations=n_relations,
        cointegration_vector=np.asarray(result.evec[:, 0], dtype=np.float64),
    )


def half_life(spread: pd.Series | np.ndarray) -> float:
    """Mean-reversion half-life via OU: regression ``Δs ~ s_lag`` -> ``-ln(2)/b``.

    Returns ``+inf`` if the spread does not revert to the mean (slope ``b >= 0``).
    """
    s = _as_array(spread)
    s_lag = sm.add_constant(s[:-1])
    slope = float(sm.OLS(np.diff(s), s_lag).fit().params[1])
    if slope >= 0.0:
        return float("inf")
    return float(-np.log(2.0) / slope)


def rolling_cointegration(
    y: pd.Series | np.ndarray, x: pd.Series | np.ndarray, *, window: int
) -> pd.DataFrame:
    """Re-estimates (β, ADF p-value) on a **trailing** rolling window, point-in-time.

    The row at instant ``i`` only uses observations ``[i-window+1, i]`` (≤ i): no
    future information enters the equilibrium estimation. The first ``window-1``
    rows are NaN (no estimation without a full window).
    """
    y_s, x_s = _as_series(y), _as_series(x)
    n = len(y_s)
    hedge = np.full(n, np.nan, dtype=np.float64)
    pvalue = np.full(n, np.nan, dtype=np.float64)
    for i in range(window - 1, n):
        sl = slice(i - window + 1, i + 1)
        eg = engle_granger(y_s.iloc[sl], x_s.iloc[sl])
        hedge[i] = eg.hedge_ratio
        pvalue[i] = eg.pvalue
    return pd.DataFrame({"hedge_ratio": hedge, "pvalue": pvalue}, index=y_s.index)
