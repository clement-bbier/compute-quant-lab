"""Convertisseurs de change $/€ (implémentent `FxConverter`).

Le prix du compute (Vast.ai / RunPod / Silicon Data) est coté en USD ; le coût
énergétique (ENTSO-E) en EUR. La conversion doit être **point-in-time** : à
chaque timestamp, on applique le taux *connu à cet instant*, jamais un taux futur.
"""

from __future__ import annotations

import pandas as pd

from core.pricing._timeindex import to_utc_index


class ConstantFx:
    """Taux de change constant (USD → EUR).

    Parameters
    ----------
    rate
        Taux EUR par USD (1 USD = ``rate`` EUR).
    """

    def __init__(self, rate: float) -> None:
        if rate <= 0:
            raise ValueError("rate doit être strictement positif")
        self._rate = rate

    def to_eur(self, amount_usd: pd.Series) -> pd.Series:
        """Convertit une série USD en EUR au taux constant."""
        return amount_usd * self._rate

    def __repr__(self) -> str:
        return f"ConstantFx(rate={self._rate})"


class SeriesFx:
    """Taux de change variable, appliqué en point-in-time.

    Le taux à l'instant ``t`` est le dernier taux *connu à* ``t`` (jointure
    as-of arrière) : on ne lit jamais un taux publié après ``t``.

    Parameters
    ----------
    rate_eur_per_usd
        Série du taux EUR/USD, index UTC tz-aware.
    """

    def __init__(self, rate_eur_per_usd: pd.Series) -> None:
        rates = rate_eur_per_usd.copy()
        rates.index = to_utc_index(rates.index)
        self._rates = rates.sort_index()

    def to_eur(self, amount_usd: pd.Series) -> pd.Series:
        """Convertit ``amount_usd`` avec le taux connu à chaque timestamp."""
        aligned = self._rates.reindex(amount_usd.index, method="ffill")
        return amount_usd * aligned

    def __repr__(self) -> str:
        return f"SeriesFx(n={len(self._rates)})"
