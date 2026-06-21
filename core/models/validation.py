"""Validation temporelle anti-overfitting (López de Prado).

Trois briques, toutes au service du risque n°1 du projet — l'overfitting :

* `PurgedKFold` — k-fold **sans shuffle** : blocs de test contigus, avec *purge* de
  l'horizon du label (on retire du train tout échantillon dont la fenêtre de label mord
  sur le test) et *embargo* (on neutralise les échantillons juste après le test, contre
  la corrélation sérielle). C'est la seule découpe correcte sur séries financières.
* `oos_predict` — assemble un vecteur de prédictions **hors-échantillon** aligné sur les
  lignes d'entrée : chaque ligne est prédite par un modèle qui ne l'a jamais vue ni vu
  son voisinage (grâce au purge/embargo). C'est ce vecteur qui devient le signal backtesté.
* `deflated_sharpe_ratio` — dégonfle le Sharpe observé par le nombre d'essais
  (`n_trials`) : plus on teste de configurations, plus un beau Sharpe arrive par hasard.

Référence : Advances in Financial Machine Learning (purged CV, embargo, deflated Sharpe).
"""

from __future__ import annotations

from typing import Callable, Iterator

import numpy as np
from scipy.stats import norm

from core.models.protocols import FloatArray, IntArray, Model

#: Constante d'Euler-Mascheroni (loi du maximum d'un échantillon gaussien).
_EULER_MASCHERONI = 0.5772156649015329


class PurgedKFold:
    """K-fold temporel purgé + embargo (implémente `Splitter`).

    Parameters
    ----------
    n_splits
        Nombre de folds (blocs de test contigus).
    horizon
        Horizon du label (en pas) : largeur de la purge à gauche du test. Un label à ``i``
        dépend de la fenêtre ``[i, i+horizon]`` ; tout train dont la fenêtre touche le test
        est retiré.
    embargo
        Nombre de pas neutralisés immédiatement après chaque bloc de test.

    Raises
    ------
    ValueError
        Si ``n_splits < 2``, ``horizon < 0`` ou ``embargo < 0``.
    """

    def __init__(self, *, n_splits: int, horizon: int = 1, embargo: int = 0) -> None:
        if n_splits < 2:
            raise ValueError(f"n_splits ({n_splits}) doit être >= 2.")
        if horizon < 0:
            raise ValueError(f"horizon ({horizon}) doit être >= 0.")
        if embargo < 0:
            raise ValueError(f"embargo ({embargo}) doit être >= 0.")
        self.n_splits = n_splits
        self.horizon = horizon
        self.embargo = embargo

    def split(self, n_samples: int) -> Iterator[tuple[IntArray, IntArray]]:
        """Itère ``(train_idx, test_idx)`` : blocs de test contigus, train purgé + embargoé."""
        if n_samples < self.n_splits:
            raise ValueError(f"n_samples ({n_samples}) < n_splits ({self.n_splits}).")
        indices = np.arange(n_samples, dtype=np.intp)
        for test in np.array_split(indices, self.n_splits):
            if test.size == 0:
                continue
            t0, t1 = int(test[0]), int(test[-1])
            mask = np.ones(n_samples, dtype=bool)
            mask[t0 : t1 + 1] = False  # le bloc de test lui-même
            mask[max(0, t0 - self.horizon) : t0] = False  # purge : label qui mord sur le test
            mask[t1 + 1 : min(n_samples, t1 + 1 + self.embargo)] = False  # embargo
            yield indices[mask], test


def oos_predict(
    make_model: Callable[[], Model],
    x: FloatArray,
    y: FloatArray,
    splitter: PurgedKFold,
) -> FloatArray:
    """Probabilités hors-échantillon alignées sur les lignes de ``x``.

    Pour chaque fold, un modèle **neuf** (``make_model()``) est entraîné sur le train purgé
    puis prédit le bloc de test. Aucune ligne n'est jamais prédite par un modèle l'ayant vue.

    Returns
    -------
    FloatArray
        Vecteur ``P(montée)`` de longueur ``len(x)`` (``NaN`` pour une ligne jamais testée).
    """
    n = x.shape[0]
    proba = np.full(n, np.nan, dtype=np.float64)
    for train, test in splitter.split(n):
        model = make_model()
        model.fit(x[train], y[train])
        proba[test] = model.predict_proba(x[test])
    return proba


def expected_max_sharpe(n_trials: int, sr_variance: float) -> float:
    """Espérance du Sharpe maximum sur ``n_trials`` essais sous l'hypothèse nulle (SR vrai = 0).

    Approximation par la loi du maximum d'un échantillon gaussien (López de Prado) :
    le seuil à battre **croît** avec le nombre d'essais — c'est le coût du multiple-testing.
    """
    if n_trials < 1:
        raise ValueError(f"n_trials ({n_trials}) doit être >= 1.")
    if n_trials == 1:
        return 0.0
    z1 = float(norm.ppf(1.0 - 1.0 / n_trials))
    z2 = float(norm.ppf(1.0 - 1.0 / (n_trials * np.e)))
    return float(np.sqrt(sr_variance) * ((1.0 - _EULER_MASCHERONI) * z1 + _EULER_MASCHERONI * z2))


def deflated_sharpe_ratio(
    observed_sr: float,
    *,
    n_obs: int,
    n_trials: int,
    sr_variance: float,
    skew: float = 0.0,
    kurtosis: float = 3.0,
) -> float:
    """Deflated Sharpe Ratio : probabilité que le vrai Sharpe soit > 0 **après** déflation.

    On compare le Sharpe observé non pas à 0 mais au maximum *attendu sous le hasard* compte
    tenu de ``n_trials`` (cf. `expected_max_sharpe`), puis on calcule un Probabilistic Sharpe
    Ratio tenant compte de la non-normalité des rendements (``skew``, ``kurtosis``).

    Parameters
    ----------
    observed_sr
        Sharpe observé (même base temporelle que ``n_obs``).
    n_obs
        Nombre d'observations de rendement.
    n_trials
        Nombre de configurations essayées (anti multiple-testing). **À logger honnêtement.**
    sr_variance
        Variance des estimations de Sharpe entre essais (dispersion de la recherche).
    skew, kurtosis
        Moments d'ordre 3 et 4 des rendements (gaussien : 0 et 3).

    Returns
    -------
    float
        Probabilité dans ``[0, 1]`` — proche de 1 = robuste, proche de 0 = illusoire.
    """
    sr_star = expected_max_sharpe(n_trials, sr_variance)
    denom = np.sqrt(1.0 - skew * observed_sr + (kurtosis - 1.0) / 4.0 * observed_sr**2)
    z = (observed_sr - sr_star) * np.sqrt(n_obs - 1) / denom
    return float(norm.cdf(z))


__all__ = [
    "PurgedKFold",
    "oos_predict",
    "expected_max_sharpe",
    "deflated_sharpe_ratio",
]
