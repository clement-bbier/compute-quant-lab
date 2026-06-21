"""Mesure du *lead* d'une feature exogène sur la cible spread (anti-overfit).

Deux outils complémentaires, volontairement simples (le prompt impose « sans
sur-fitter ») :

* `cross_correlations` — corrélation feature(t) vs cible(t+k) pour k = 0..K.
  Transparente, robuste, sans modèle. Donne le lag optimal.
* `confirm_ols` — régression de confirmation au lag optimal, **split temporel
  strict** (pas de shuffle, cf. rule no-look-ahead) et R² out-of-sample.

Fonctions pures (aucune I/O) : testables sur fixtures connues.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import statsmodels.api as sm


def cross_correlations(
    feature: pd.Series,
    target: pd.Series,
    max_lag: int,
    method: str = "pearson",
) -> pd.Series:
    """Corrélation de ``feature(t)`` avec ``target(t + k)`` pour ``k = 0..max_lag``.

    Un ``k`` positif où la corrélation culmine signifie que la feature **précède**
    la cible de ``k`` pas (pouvoir prédictif / lead).
    """
    correlations: dict[int, float] = {}
    for k in range(max_lag + 1):
        pair = pd.concat([feature, target.shift(-k)], axis=1).dropna()
        correlations[k] = (
            float(pair.iloc[:, 0].corr(pair.iloc[:, 1], method=method))
            if len(pair) >= 3
            else float("nan")
        )
    return pd.Series(correlations, name=f"xcorr_{method}")


def best_lag(corr: pd.Series) -> int:
    """Lag de corrélation absolue maximale (le lead le plus marqué)."""
    return int(corr.abs().idxmax())


def confirm_ols(
    feature: pd.Series,
    target: pd.Series,
    lag: int,
    train_frac: float = 0.7,
) -> dict[str, Any]:
    """OLS de confirmation ``target(t+lag) ~ feature(t)`` avec split temporel strict.

    Le split est chronologique (les ``train_frac`` premières observations servent
    d'entraînement, le reste de test) : aucune fuite train→test sur la série
    temporelle. Renvoie coefficient, p-value et R² in-sample / out-of-sample.
    """
    aligned = pd.concat([feature.rename("x"), target.shift(-lag).rename("y")], axis=1).dropna()
    n_train = int(len(aligned) * train_frac)
    train, test = aligned.iloc[:n_train], aligned.iloc[n_train:]

    model = sm.OLS(train["y"], sm.add_constant(train["x"])).fit()
    pred = model.predict(sm.add_constant(test["x"], has_constant="add"))
    ss_res = float(((test["y"] - pred) ** 2).sum())
    ss_tot = float(((test["y"] - test["y"].mean()) ** 2).sum())
    r2_oos = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")

    return {
        "lag": int(lag),
        "coef": float(model.params["x"]),
        "intercept": float(model.params["const"]),
        "pvalue": float(model.pvalues["x"]),
        "r2_in": float(model.rsquared),
        "r2_oos": float(r2_oos),
        "n_train": int(len(train)),
        "n_test": int(len(test)),
    }
