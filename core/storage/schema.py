"""Schéma canonique du cold store compute et normalisation de frame.

Un seul endroit définit les colonnes du lac de prix et garantit leurs types
(horodatage UTC tz-aware, prix flottant, dispo entière). Les writers (collecteur,
migration) et les readers (Parquet, DuckDB) s'y réfèrent : le schéma ne vit pas en
dur dans la logique (rule qualité Python).

Garantie d'intégrité : un horodatage naïf est **rejeté** (rule data-integrity — pas
de point-in-time ambigu), jamais silencieusement localisé.
"""

from __future__ import annotations

import pandas as pd

#: Instant du relevé (UTC tz-aware).
SNAPSHOTTED_AT = "snapshotted_at"
#: Marketplace d'origine (``vastai``, ``runpod``, …) — colonne de partition.
SOURCE = "source"
#: Famille GPU canonique (``H100``, …).
GPU_MODEL = "gpu_model"
#: Type de bail (``on_demand`` / ``spot`` / ``reserved``) — jamais agrégés ensemble.
LEASE_TYPE = "lease_type"
#: Prix en USD par GPU·heure.
PRICE = "price_usd_per_hour"
#: Nombre de GPU offerts (proxy de profondeur du relevé).
AVAILABILITY = "availability"

#: Colonnes métier du cold store, dans l'ordre canonique.
COLUMNS: list[str] = [SNAPSHOTTED_AT, SOURCE, GPU_MODEL, LEASE_TYPE, PRICE, AVAILABILITY]


def normalize_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Projette ``frame`` sur le schéma canonique et force ses dtypes.

    Parameters
    ----------
    frame
        Frame contenant au moins :data:`COLUMNS` (colonnes surnuméraires ignorées,
        ex. la partition ``month`` relue depuis Parquet).

    Returns
    -------
    pandas.DataFrame
        Copie typée : ``snapshotted_at`` en ``datetime64[ns, UTC]``, ``price`` en
        ``float64``, ``availability`` en ``int64``, identifiants en ``str``.

    Raises
    ------
    ValueError
        Si une colonne du schéma manque, ou si ``snapshotted_at`` contient des
        instants naïfs (sans fuseau) — interdits (intégrité point-in-time).
    """
    missing = [c for c in COLUMNS if c not in frame.columns]
    if missing:
        raise ValueError(f"Colonnes manquantes pour le schéma cold store : {missing}.")

    out = frame.loc[:, COLUMNS].copy()
    ts = pd.to_datetime(out[SNAPSHOTTED_AT])
    if getattr(ts.dtype, "tz", None) is None:
        if len(ts) > 0:
            raise ValueError("snapshotted_at naïf interdit : fournir un datetime tz-aware (UTC).")
        ts = ts.dt.tz_localize("UTC")
    else:
        ts = ts.dt.tz_convert("UTC")

    out[SNAPSHOTTED_AT] = ts
    out[SOURCE] = out[SOURCE].astype(str)
    out[GPU_MODEL] = out[GPU_MODEL].astype(str)
    out[LEASE_TYPE] = out[LEASE_TYPE].astype(str)
    out[PRICE] = out[PRICE].astype("float64")
    out[AVAILABILITY] = out[AVAILABILITY].astype("int64")
    return out.reset_index(drop=True)
