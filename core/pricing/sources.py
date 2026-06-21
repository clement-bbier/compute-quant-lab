"""Source de prix adossée à des DataFrames pandas (pure, point-in-time).

Enveloppe deux frames alignés en UTC — énergie (€/MWh, colonnes = régions) et
compute ($/GPU·h, colonnes = GPU) — et les expose via le protocole `PriceSource`.

Le mécanisme *as-of* (`publication_lag`) est codé mais **inactif par défaut**
(lag = 0) : à lag nul, l'instant de connaissance d'une valeur est son propre
timestamp. Le décalage réel s'activera au palier institutionnel (compute publié
avec retard), sans changer l'interface.
"""

from __future__ import annotations

import pandas as pd

from core.pricing._timeindex import to_utc_index


def _normalise(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out.index = to_utc_index(out.index)
    return out.sort_index()


class DataFramePriceSource:
    """Source de prix en mémoire (implémente `PriceSource`).

    Parameters
    ----------
    energy
        Prix spot élec en €/MWh ; index UTC tz-aware, colonnes = régions.
    compute
        Prix de location compute en $/GPU·h ; index UTC tz-aware, colonnes = GPU.
    energy_lag, compute_lag
        Décalage de publication par jambe (instant de connaissance = timestamp
        de la valeur + lag). Par défaut nul. Accepte tout objet `Timedelta`.
    """

    def __init__(
        self,
        energy: pd.DataFrame,
        compute: pd.DataFrame,
        *,
        energy_lag: pd.Timedelta | str = "0h",
        compute_lag: pd.Timedelta | str = "0h",
    ) -> None:
        self._energy = _normalise(energy)
        self._compute = _normalise(compute)
        self._energy_lag = pd.Timedelta(energy_lag)
        self._compute_lag = pd.Timedelta(compute_lag)

    @staticmethod
    def _apply_lag(series: pd.Series, lag: pd.Timedelta) -> pd.Series:
        """Décale l'index vers l'instant de *connaissance* (value_ts + lag)."""
        if lag == pd.Timedelta(0):
            return series
        shifted = series.copy()
        shifted.index = shifted.index + lag
        return shifted

    def energy_price(self, region: str) -> pd.Series:
        """Prix spot de l'électricité en €/MWh pour ``region`` (index UTC)."""
        return self._apply_lag(self._energy[region], self._energy_lag)

    def compute_price(self, gpu: str) -> pd.Series:
        """Prix de location du compute en $/GPU·h pour ``gpu`` (index UTC)."""
        return self._apply_lag(self._compute[gpu], self._compute_lag)
