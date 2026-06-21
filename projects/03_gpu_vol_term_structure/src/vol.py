"""Estimateurs de volatilité de l'indice spot compute (point-in-time, purs).

La volatilité des prix GPU est traitée comme un actif : ce module en fournit deux
estimateurs **causals** et interchangeables (pattern Strategy / DI), opérant sur une
série de log-returns et renvoyant une série de vol **annualisée** :

- :class:`RealizedVol` — écart-type glissant sur fenêtre trailing (vol réalisée) ;
- :class:`EwmaVol` — récursion RiskMetrics (poids exponentiels, réactive).

Garantie anti look-ahead (rule ``quant-no-lookahead``) : ``vol[t]`` ne dépend que des
returns d'indice ≤ t — vérifié par invariance à la troncature de la série.

Le :class:`VolEstimator` (Protocol) ouvre l'extension à un futur ``GarchVol`` sans
toucher aux consommateurs (Open/Closed). On reste en numpy pur (aucune dépendance neuve).

Unités : ``periods_per_year`` est nommé (pas de nombre magique). Le compute se traite en
continu (24/7) → défaut 365 jours.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import numpy as np

#: Facteur d'annualisation par défaut : compute tradé en continu (jours calendaires).
DEFAULT_PERIODS_PER_YEAR = 365.0


def log_returns(prices: np.ndarray) -> np.ndarray:
    """Log-returns d'une série de prix strictement positifs.

    Parameters
    ----------
    prices
        Série de prix (1D), strictement positive.

    Returns
    -------
    numpy.ndarray
        ``log(P[t] / P[t-1])`` ; longueur ``len(prices) - 1``.
    """
    prices = np.asarray(prices, dtype=float)
    if prices.ndim != 1 or prices.size < 2:
        raise ValueError("log_returns attend une série 1D d'au moins 2 prix.")
    if np.any(prices <= 0.0):
        raise ValueError("log_returns exige des prix strictement positifs.")
    return np.diff(np.log(prices))


@runtime_checkable
class VolEstimator(Protocol):
    """Estimateur de volatilité injectable (Strategy).

    Toute implémentation renvoie une série de vol annualisée **causale**, alignée sur
    les returns en entrée. Point d'extension pour un ``GarchVol`` (palier institutionnel).
    """

    @property
    def name(self) -> str:
        """Identifiant court tracé dans MLflow (ex. ``ewma0.94``)."""
        ...

    def estimate(self, returns: np.ndarray) -> np.ndarray:
        """Série de vol annualisée ; ``vol[t]`` n'utilise que ``returns[≤ t]``."""
        ...


@dataclass(frozen=True)
class RealizedVol:
    """Vol réalisée : écart-type glissant des returns sur une fenêtre trailing.

    ``vol[t]`` agrège ``returns[t-window+1 .. t]`` (inclus), donc strictement
    point-in-time. Le warmup (``t < window-1``) vaut ``NaN``.
    """

    window: int
    periods_per_year: float = DEFAULT_PERIODS_PER_YEAR
    ddof: int = 1

    def __post_init__(self) -> None:
        if self.window < 2:
            raise ValueError("window doit être >= 2 pour un écart-type.")

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
    """Vol EWMA (RiskMetrics) : variance à poids exponentiels, réactive.

    Récursion filtrée causale ``var[t] = λ·var[t-1] + (1-λ)·r[t]²`` (seed ``var[0]=r[0]²``).
    ``vol[t]`` ne dépend que de ``returns[≤ t]`` ; ``vol[t] = sqrt(var[t]·periods_per_year)``.
    """

    lam: float
    periods_per_year: float = DEFAULT_PERIODS_PER_YEAR

    def __post_init__(self) -> None:
        if not 0.0 < self.lam < 1.0:
            raise ValueError("lam (λ) doit être dans (0, 1).")

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
