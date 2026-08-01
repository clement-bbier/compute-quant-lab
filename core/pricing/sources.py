"""Price source backed by pandas DataFrames (pure, point-in-time).

Wraps two UTC-aligned frames -- energy (€/MWh, columns = regions) and compute
($/GPU·h, columns = GPUs) -- and exposes them through the `PriceSource` protocol.

The *as-of* mechanism (`publication_lag`) is implemented but **inactive by default**
(lag = 0): at zero lag, the instant a value becomes known is its own timestamp. The
real lag will be switched on at the institutional stage (compute published with a
delay), without changing the interface.
"""

from __future__ import annotations

import pandas as pd

from core.pricing._timeindex import to_utc_index


def _normalise(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out.index = to_utc_index(out.index)
    return out.sort_index()


class DataFramePriceSource:
    """In-memory price source (implements `PriceSource`).

    Parameters
    ----------
    energy
        Spot electricity price in €/MWh; tz-aware UTC index, columns = regions.
    compute
        Compute rental price in $/GPU·h; tz-aware UTC index, columns = GPUs.
    energy_lag, compute_lag
        Publication lag per leg (the instant a value becomes known = the timestamp of
        the value + lag). Zero by default. Accepts any `Timedelta`-like object.
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
        """Shift the index to the instant of *knowledge* (value_ts + lag)."""
        if lag == pd.Timedelta(0):
            return series
        shifted = series.copy()
        shifted.index = shifted.index + lag
        return shifted

    def energy_price(self, region: str) -> pd.Series:
        """Spot electricity price in €/MWh for ``region`` (UTC index)."""
        return self._apply_lag(self._energy[region], self._energy_lag)

    def compute_price(self, gpu: str) -> pd.Series:
        """Compute rental price in $/GPU·h for ``gpu`` (UTC index)."""
        return self._apply_lag(self._compute[gpu], self._compute_lag)
