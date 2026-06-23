"""Builder de label « spike RTM » ERCOT (fiche L0 §4-§5) — fonctions pures.

Label primaire L0 : prix RTM **horaire intégré** > 99e percentile **conditionnel à
l'heure-de-jour**, fenêtre **trailing causale**. Robustesse : seuil absolu > $1500/MWh.

Storage-agnostique : consomme une série de prix (fournie depuis le cold store
versionné au moment du run de calibration, cf. rule training-cold-store). Aucune I/O.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def to_hourly_integrated(price: pd.Series) -> pd.Series:
    """Intègre une série de prix infra-horaire (RTM 15 min) en moyenne horaire.

    La moyenne d'intervalles de durée égale = prix horaire intégré : filtre les blips
    de microstructure (un pic isolé de 5 min ne déclenche pas un spike horaire).
    """
    if price.index.tz is None:
        raise ValueError("index UTC tz-aware obligatoire")
    return price.sort_index().resample("1h").mean().dropna()


def spike_label_absolute(hourly: pd.Series, threshold_usd_mwh: float = 1500.0) -> pd.Series:
    """Label spike absolu : prix horaire > seuil (robustesse L0, défaut $1500/MWh)."""
    return (hourly > threshold_usd_mwh).rename("spike")


def spike_label_hod_percentile(
    hourly: pd.Series,
    *,
    pct: float = 0.99,
    min_obs_per_hour: int = 30,
) -> pd.Series:
    """Label spike **primaire** L0 : > ``pct`` conditionnel heure-de-jour, trailing causal.

    Pour chaque instant ``t`` (heure-de-jour ``h``), le seuil est le quantile ``pct``
    des prix **passés** (index strictement ``< t``) à la même heure-de-jour ``h``.
    Strictement causal : aucune valeur à/après ``t`` n'entre dans son propre seuil
    (anti look-ahead). ``False`` si l'historique de l'heure ``h`` est insuffisant
    (``< min_obs_per_hour``).

    Parameters
    ----------
    hourly
        Prix horaire intégré (UTC tz-aware).
    pct
        Quantile conditionnel (défaut 0.99, fiche L0).
    min_obs_per_hour
        Nombre minimal d'observations passées à la même heure-de-jour pour estimer
        le seuil (sinon ``False``).
    """
    if not 0.0 < pct < 1.0:
        raise ValueError("pct doit être dans (0, 1)")
    hourly = hourly.sort_index()
    hours = np.asarray(hourly.index.hour)
    values = hourly.to_numpy(dtype=float)
    out = np.zeros(len(values), dtype=bool)
    for i in range(len(values)):
        past = values[:i][hours[:i] == hours[i]]
        if past.size < min_obs_per_hour:
            continue
        out[i] = bool(values[i] > np.quantile(past, pct))
    return pd.Series(out, index=hourly.index, name="spike")
