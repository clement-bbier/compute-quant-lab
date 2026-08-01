"""USD/EUR FX converters (implement `FxConverter`).

The price of compute (Vast.ai / RunPod / Silicon Data) is quoted in USD, while the
energy cost (ENTSO-E) is in EUR. The conversion must be **point-in-time**: at each
timestamp the rate *known at that instant* is applied, never a future rate.
"""

from __future__ import annotations

import pandas as pd

from core.pricing._timeindex import to_utc_index


class ConstantFx:
    """Constant exchange rate (USD to EUR).

    Parameters
    ----------
    rate
        Rate in EUR per USD (1 USD = ``rate`` EUR).
    """

    def __init__(self, rate: float) -> None:
        if rate <= 0:
            raise ValueError("rate must be strictly positive.")
        self._rate = rate

    def to_eur(self, amount_usd: pd.Series) -> pd.Series:
        """Convert a USD series to EUR at the constant rate."""
        return amount_usd * self._rate

    def __repr__(self) -> str:
        return f"ConstantFx(rate={self._rate})"


class SeriesFx:
    """Time-varying exchange rate, applied point-in-time.

    The rate at instant ``t`` is the last rate *known at* ``t`` (backward as-of
    join): a rate published after ``t`` is never read.

    Parameters
    ----------
    rate_eur_per_usd
        EUR/USD rate series, tz-aware UTC index.
    """

    def __init__(self, rate_eur_per_usd: pd.Series) -> None:
        rates = rate_eur_per_usd.copy()
        rates.index = to_utc_index(rates.index)
        self._rates = rates.sort_index()

    def to_eur(self, amount_usd: pd.Series) -> pd.Series:
        """Convert ``amount_usd`` with the rate known at each timestamp."""
        aligned = self._rates.reindex(amount_usd.index, method="ffill")
        return amount_usd * aligned

    def __repr__(self) -> str:
        return f"SeriesFx(n={len(self._rates)})"
