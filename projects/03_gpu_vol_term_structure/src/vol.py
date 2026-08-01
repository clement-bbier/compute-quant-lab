"""Compute spot index volatility estimators (point-in-time, pure).

GPU price volatility is treated as an asset: this module provides two
**causal** and interchangeable estimators (Strategy / DI pattern), operating on a
series of log-returns and returning an **annualized** vol series:

- :class:`RealizedVol` — rolling standard deviation over a trailing window (realized vol);
- :class:`EwmaVol` — RiskMetrics recursion (exponential weights, reactive).

Anti look-ahead guarantee (rule ``quant-no-lookahead``): ``vol[t]`` depends only on
index returns ≤ t — verified by invariance to series truncation.

The :class:`VolEstimator` (Protocol) opens the extension to a future ``GarchVol`` without
touching consumers (Open/Closed). We stay in pure numpy (no new dependency).

Units: ``periods_per_year`` is named (no magic number). Compute trades
continuously (24/7) → default 365 days.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import numpy as np

#: Default annualization factor: compute traded continuously (calendar days).
DEFAULT_PERIODS_PER_YEAR = 365.0


def log_returns(prices: np.ndarray) -> np.ndarray:
    """Log-returns of a strictly positive price series.

    Parameters
    ----------
    prices
        Price series (1D), strictly positive.

    Returns
    -------
    numpy.ndarray
        ``log(P[t] / P[t-1])``; length ``len(prices) - 1``.
    """
    prices = np.asarray(prices, dtype=float)
    if prices.ndim != 1 or prices.size < 2:
        raise ValueError("log_returns expects a 1D series of at least 2 prices.")
    if np.any(prices <= 0.0):
        raise ValueError("log_returns requires strictly positive prices.")
    return np.diff(np.log(prices))


@runtime_checkable
class VolEstimator(Protocol):
    """Injectable volatility estimator (Strategy).

    Any implementation returns a **causal** annualized vol series, aligned with
    the input returns. Extension point for a ``GarchVol`` (institutional tier).
    """

    @property
    def name(self) -> str:
        """Short identifier logged in MLflow (e.g. ``ewma0.94``)."""
        ...

    def estimate(self, returns: np.ndarray) -> np.ndarray:
        """Annualized vol series; ``vol[t]`` uses only ``returns[≤ t]``."""
        ...


@dataclass(frozen=True)
class RealizedVol:
    """Realized vol: rolling standard deviation of returns over a trailing window.

    ``vol[t]`` aggregates ``returns[t-window+1 .. t]`` (inclusive), so it is strictly
    point-in-time. The warmup (``t < window-1``) is ``NaN``.
    """

    window: int
    periods_per_year: float = DEFAULT_PERIODS_PER_YEAR
    ddof: int = 1

    def __post_init__(self) -> None:
        if self.window < 2:
            raise ValueError("window must be >= 2 for a standard deviation.")

    @property
    def name(self) -> str:
        return f"realized{self.window}"

    def estimate(self, returns: np.ndarray) -> np.ndarray:
        r = np.asarray(returns, dtype=float)
        n = r.size
        vol = np.full(n, np.nan, dtype=float)
        if n < self.window:
            return vol
        windows = np.lib.stride_tricks.sliding_window_view(r, self.window)
        stds = windows.std(axis=1, ddof=self.ddof)
        vol[self.window - 1 :] = stds * np.sqrt(self.periods_per_year)
        return vol


@dataclass(frozen=True)
class EwmaVol:
    """EWMA vol (RiskMetrics): exponentially weighted variance, reactive.

    Causal filtered recursion ``var[t] = λ·var[t-1] + (1-λ)·r[t]²`` (seeded with ``var[0]=r[0]²``).
    ``vol[t]`` depends only on ``returns[≤ t]``; ``vol[t] = sqrt(var[t]·periods_per_year)``.
    """

    lam: float
    periods_per_year: float = DEFAULT_PERIODS_PER_YEAR

    def __post_init__(self) -> None:
        if not 0.0 < self.lam < 1.0:
            raise ValueError("lam (λ) must be in (0, 1).")

    @property
    def name(self) -> str:
        return f"ewma{self.lam}"

    def estimate(self, returns: np.ndarray) -> np.ndarray:
        r = np.asarray(returns, dtype=float)
        n = r.size
        var = np.empty(n, dtype=float)
        if n == 0:
            return var
        var[0] = r[0] ** 2
        for t in range(1, n):
            var[t] = self.lam * var[t - 1] + (1.0 - self.lam) * r[t] ** 2
        return np.sqrt(var * self.periods_per_year)
