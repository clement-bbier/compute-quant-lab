"""Dataset de calibration L0 ERCOT depuis le cold store (point-in-time strict).

Pour chaque jour cible J, reconstruit les deux prédicteurs gelés de L0 — **marge de
réserve** (capacité STSA − net-load, cf. L0-v2) et **gradient net-load** — tels que connus à la
décision ``as_of ≈ 18h CPT J-1`` (≈ 23h UTC en CDT), puis les aligne sur le **label
spike RTM** réalisé des heures de J.

Lit le **Parquet versionné** (rule training-cold-store), jamais le live. Le garde-fou
look-ahead vit dans :func:`_latest_per_interval_long` (``publish_time <= as_of``) — une
prévision révisée après le cutoff n'entre jamais dans le prédicteur du jour.
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

#: Heure UTC du cutoff de décision (~18h CPT J-1 = 23h UTC en CDT été).
DEFAULT_AS_OF_UTC_HOUR = 23


def _latest_per_interval_long(df: pd.DataFrame, as_of: pd.Timestamp) -> pd.Series:
    """``interval_start`` → dernière valeur publiée ``<= as_of`` (garde-fou look-ahead)."""
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
    """Construit ``(X[reserve_margin, net_load_gradient], y[spike], index)`` aligné point-in-time.

    ``label`` : ``"hod"`` (99e pct conditionnel heure-de-jour) ou ``"abs"`` (> seuil $/MWh).
    Ne garde que les lignes où **les deux prédicteurs** sont disponibles.
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
        day_idx = grp.index  # intervalles cibles (horaires) du jour J
        # Alignement VECTORISÉ par reindex (robuste sur grilles mixtes). L0-v2 : la marge
        # est capacité − net-load (la charge brute 7 j est indisponible à l'horizon 18h J-1).
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
