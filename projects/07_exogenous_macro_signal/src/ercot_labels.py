"""ERCOT "RTM spike" label builder (L0 spec §4-§5) — pure functions.

Primary L0 label: **hourly-integrated** RTM price > 99th percentile **conditional on
hour-of-day**, **causal trailing** window. Robustness check: absolute threshold > $1500/MWh.

Storage-agnostic: consumes a price series (supplied from the versioned cold store
at calibration run time, cf. rule training-cold-store). No I/O.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def to_hourly_integrated(price: pd.Series) -> pd.Series:
    """Integrates a sub-hourly (15-min RTM) price series into an hourly average.

    The mean of equal-duration intervals = hourly-integrated price: filters out
    microstructure blips (an isolated 5-min spike does not trigger an hourly spike).
    """
    if price.index.tz is None:
        raise ValueError("UTC tz-aware index required")
    return price.sort_index().resample("1h").mean().dropna()


def spike_label_absolute(hourly: pd.Series, threshold_usd_mwh: float = 1500.0) -> pd.Series:
    """Absolute spike label: hourly price > threshold (L0 robustness check, default $1500/MWh)."""
    return (hourly > threshold_usd_mwh).rename("spike")


def spike_label_hod_percentile(
    hourly: pd.Series,
    *,
    pct: float = 0.99,
    min_obs_per_hour: int = 30,
) -> pd.Series:
    """**Primary** L0 spike label: > ``pct`` conditional on hour-of-day, causal trailing.

    For each instant ``t`` (hour-of-day ``h``), the threshold is the ``pct`` quantile
    of **past** prices (index strictly ``< t``) at the same hour-of-day ``h``.
    Strictly causal: no value at/after ``t`` enters its own threshold
    (anti-look-ahead). ``False`` if the history for hour ``h`` is insufficient
    (``< min_obs_per_hour``).

    Parameters
    ----------
    hourly
        Hourly-integrated price (UTC tz-aware).
    pct
        Conditional quantile (default 0.99, per the L0 spec).
    min_obs_per_hour
        Minimum number of past observations at the same hour-of-day needed to
        estimate the threshold (otherwise ``False``).
    """
    if not 0.0 < pct < 1.0:
        raise ValueError("pct must be in (0, 1)")
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
