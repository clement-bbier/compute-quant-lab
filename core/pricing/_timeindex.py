"""Validation et normalisation des index temporels (UTC tz-aware).

Centralise la règle d'intégrité des données du labo : *tous les timestamps sont
en UTC, timezone-aware ; pas de datetime naïf*. Réutilisé par les sources de
prix et les convertisseurs FX pour garantir une frontière unique et testée.
"""

from __future__ import annotations

import pandas as pd


def to_utc_index(index: pd.Index) -> pd.DatetimeIndex:
    """Valide qu'un index est temporel tz-aware et le ramène en UTC.

    Parameters
    ----------
    index
        Index à valider.

    Returns
    -------
    pd.DatetimeIndex
        Le même index converti en UTC.

    Raises
    ------
    ValueError
        Si l'index n'est pas un `DatetimeIndex` ou s'il est tz-naïf.
    """
    if not isinstance(index, pd.DatetimeIndex):
        raise ValueError("l'index doit être un DatetimeIndex")
    if index.tz is None:
        raise ValueError("datetime naïf interdit : index UTC tz-aware obligatoire")
    return index.tz_convert("UTC")
