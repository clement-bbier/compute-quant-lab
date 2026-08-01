"""ERCOT L0 calibration dataset from the cold store (strict point-in-time).

For each target day D, rebuilds the two frozen L0 predictors — **reserve
margin** (STSA capacity minus net-load, cf. L0-v2) and **net-load gradient** — as known at the
``as_of ≈ 6pm CPT D-1`` decision point (≈ 11pm UTC in CDT), then aligns them with the
realized **RTM spike label** for the hours of D.

Reads the **versioned Parquet** (rule training-cold-store), never the live feed. The
look-ahead guard lives in :func:`_latest_per_interval_long` (``publish_time <= as_of``) — a
forecast revised after the cutoff never enters that day's predictor.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from core.storage.energy_store import INTERVAL_START, PUBLISH_TIME, VALUE, EnergyColdStore
from ercot_labels import (
    spike_label_absolute,
    spike_label_hod_percentile,
    to_hourly_integrated,
)

#: UTC hour of the decision cutoff (~6pm CPT D-1 = 11pm UTC in summer CDT).
DEFAULT_AS_OF_UTC_HOUR = 23


def _latest_per_interval_long(df: pd.DataFrame, as_of: pd.Timestamp) -> pd.Series:
    """``interval_start`` -> latest value published ``<= as_of`` (look-ahead guard)."""
    known = df[df[PUBLISH_TIME] <= as_of]
    if known.empty:
        return pd.Series(dtype=float)
    latest = known.loc[known.groupby(INTERVAL_START)[PUBLISH_TIME].idxmax()]
    return pd.Series(
        latest[VALUE].to_numpy(dtype=float),
        index=pd.DatetimeIndex(latest[INTERVAL_START]),
    ).sort_index()


def build_calibration_dataset(
    store: EnergyColdStore,
    *,
    as_of_utc_hour: int = DEFAULT_AS_OF_UTC_HOUR,
    label: str = "hod",
    pct: float = 0.99,
    min_obs_per_hour: int = 20,
    threshold_usd_mwh: float = 1500.0,
) -> tuple[np.ndarray, np.ndarray, pd.DatetimeIndex]:
    """Builds ``(X[reserve_margin, net_load_gradient], y[spike], index)`` aligned point-in-time.

    ``label``: ``"hod"`` (hour-of-day conditional 99th pct) or ``"abs"`` (> $/MWh threshold).
    Keeps only rows where **both predictors** are available.
    """
    rtm = store.read(series="rtm_spp")
    cap = store.read(series="available_capacity")
    nl = store.read(series="net_load_forecast")

    price = pd.Series(rtm[VALUE].to_numpy(dtype=float), index=pd.DatetimeIndex(rtm[INTERVAL_START]))
    hourly = to_hourly_integrated(price)
    if label == "abs":
        y_all = spike_label_absolute(hourly, threshold_usd_mwh=threshold_usd_mwh)
    else:
        y_all = spike_label_hod_percentile(hourly, pct=pct, min_obs_per_hour=min_obs_per_hour)

    parts: list[pd.DataFrame] = []
    target = pd.Series(y_all.to_numpy(), index=y_all.index)
    for day, grp in target.groupby(target.index.normalize()):
        as_of = pd.Timestamp(day) - pd.Timedelta(days=1) + pd.Timedelta(hours=as_of_utc_hour)
        day_idx = grp.index  # target (hourly) intervals for day D
        # VECTORIZED alignment via reindex (robust across mixed grids). L0-v2: the margin
        # is capacity minus net-load (raw 7-day load is unavailable at the 6pm D-1 horizon).
        nl_known = _latest_per_interval_long(nl, as_of)
        cap_k = _latest_per_interval_long(cap, as_of).reindex(day_idx)
        net_k = nl_known.reindex(day_idx)
        grad = nl_known.diff().reindex(day_idx)
        parts.append(
            pd.DataFrame(
                {
                    "interval_start": day_idx,
                    "reserve_margin_mw": (cap_k - net_k).to_numpy(),
                    "net_load_gradient_mw": grad.to_numpy(),
                    "spike": grp.to_numpy(),
                }
            )
        )

    if not parts:
        return np.empty((0, 2)), np.empty(0), pd.DatetimeIndex([], tz="UTC")
    frame = (
        pd.concat(parts, ignore_index=True)
        .dropna(subset=["reserve_margin_mw", "net_load_gradient_mw"])
        .reset_index(drop=True)
    )
    x = frame[["reserve_margin_mw", "net_load_gradient_mw"]].to_numpy(dtype=float)
    y = frame["spike"].to_numpy(dtype=float)
    return x, y, pd.DatetimeIndex(frame["interval_start"])
