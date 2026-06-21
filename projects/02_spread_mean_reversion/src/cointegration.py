"""Boîte à outils de cointégration énergie↔compute (fondement de l'arbitrage de spread).

Deux séries corrélées par hasard (corrélation fallacieuse) n'autorisent aucun arbitrage :
on teste une vraie relation d'équilibre de long terme avant de shorter un spread. Ce module
fournit le protocole complet de la skill ``/cointegration-analysis`` :

1. Stationnarité (ADF + KPSS).
2. Cointégration : Engle-Granger (2 séries, hedge ratio + résidu) et Johansen (≥ 2 séries).
3. Demi-vie de retour à la moyenne (Ornstein-Uhlenbeck).
4. Stabilité : ré-estimation **point-in-time** sur fenêtre glissante (anti look-ahead, anti-spurious).

Fonctions pures (aucune I/O), résultats immuables et auditables.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.stattools import adfuller, coint, kpss
from statsmodels.tsa.vector_ar.vecm import coint_johansen

#: Indice du seuil critique à 95 % dans les tables de ``coint_johansen`` ([90 %, 95 %, 99 %]).
_CRIT_95 = 1


def _as_array(series: pd.Series | np.ndarray) -> np.ndarray:
    """Vue float64 1-D d'une série/tableau (unité de travail des tests statistiques)."""
    return np.asarray(series, dtype=np.float64)


def _as_series(series: pd.Series | np.ndarray) -> pd.Series:
    """Série pandas (préserve l'index temporel s'il existe, sinon RangeIndex)."""
    return (
        series if isinstance(series, pd.Series) else pd.Series(np.asarray(series, dtype=np.float64))
    )


@dataclass(frozen=True)
class StationarityResult:
    """Résultat d'un test de stationnarité (ADF ou KPSS)."""

    statistic: float
    pvalue: float
    is_stationary: bool


@dataclass(frozen=True)
class EngleGrangerResult:
    """Cointégration à deux séries : ``y = intercept + hedge_ratio·x + résidu``."""

    hedge_ratio: float
    intercept: float
    residuals: pd.Series
    pvalue: float
    is_cointegrated: bool


@dataclass(frozen=True)
class JohansenResult:
    """Test de Johansen : statistiques de trace vs seuils 95 % + vecteur de cointégration."""

    trace_stats: np.ndarray
    trace_crit_95: np.ndarray
    n_relations: int
    cointegration_vector: np.ndarray


def adf_test(series: pd.Series | np.ndarray, *, alpha: float = 0.05) -> StationarityResult:
    """Augmented Dickey-Fuller. Hypothèse nulle = racine unitaire ; stationnaire si p < ``alpha``."""
    stat, pvalue, *_ = adfuller(_as_array(series), autolag="AIC")
    return StationarityResult(float(stat), float(pvalue), bool(pvalue < alpha))


def kpss_test(series: pd.Series | np.ndarray, *, alpha: float = 0.05) -> StationarityResult:
    """KPSS. Hypothèse nulle = **stationnarité** ; stationnaire si p > ``alpha`` (on ne rejette pas)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # p-value interpolée hors table : sans conséquence ici
        stat, pvalue, *_ = kpss(_as_array(series), regression="c", nlags="auto")
    return StationarityResult(float(stat), float(pvalue), bool(pvalue > alpha))


def engle_granger(
    y: pd.Series | np.ndarray, x: pd.Series | np.ndarray, *, alpha: float = 0.05
) -> EngleGrangerResult:
    """Engle-Granger : OLS ``y ~ x`` pour le hedge ratio, p-value de cointégration via ``coint``.

    La p-value vient de ``statsmodels.coint`` (valeurs critiques MacKinnon) et **non** d'un ADF
    brut sur le résidu : le résidu provient d'une régression où β est estimé, ce qui sur-rejette
    et fabrique de la cointégration fallacieuse. Le résidu OLS reste exposé (spread à trader).
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
    """Test de Johansen (trace). ``n_relations`` = nombre de rejets successifs depuis le rang 0."""
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
    """Demi-vie de retour à la moyenne via OU : régression ``Δs ~ s_lag`` → ``-ln(2)/b``.

    Renvoie ``+inf`` si le spread ne revient pas à la moyenne (pente ``b ≥ 0``).
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
    """Ré-estime (β, p-value ADF) sur une fenêtre glissante **trailing**, point-in-time.

    La ligne à l'instant ``i`` n'utilise que les observations ``[i-window+1, i]`` (≤ i) : aucune
    information future n'entre dans l'estimation de l'équilibre. Les ``window-1`` premières
    lignes sont NaN (pas d'estimation sans fenêtre complète).
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
