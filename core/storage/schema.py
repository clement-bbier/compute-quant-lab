"""Schéma canonique du cold store compute et normalisation de frame.

Un seul endroit définit les colonnes du lac de prix et garantit leurs types
(horodatage UTC tz-aware, prix flottant, dispo entière). Les writers (collecteur,
migration) et les readers (Parquet, DuckDB) s'y réfèrent : le schéma ne vit pas en
dur dans la logique (rule qualité Python).

Garantie d'intégrité : un horodatage naïf est **rejeté** (rule data-integrity — pas
de point-in-time ambigu), jamais silencieusement localisé.

Rétrocompatibilité : les colonnes descriptives optionnelles (``region``,
``gpu_memory_gb``, ``vcpu``, ``ram_gb``, ``disk_gb``, ``provider_detail``) sont
tolérées-absentes. Un Parquet écrit avant leur ajout est rechargeable sans erreur :
``normalize_frame`` les backfille avec ``None``/``NaN``.
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

# ── Colonnes descriptives optionnelles (ajoutées post-fondation) ──────────────
#: Région / datacenter d'hébergement (ex. ``"EU-FIN-01"``, ``"us-east"``).
REGION = "region"
#: Mémoire GPU en Go (ex. ``80.0`` pour un H100 SXM).
GPU_MEMORY_GB = "gpu_memory_gb"
#: Nombre de vCPU de l'instance.
VCPU = "vcpu"
#: RAM de l'instance en Go.
RAM_GB = "ram_gb"
#: Stockage de l'instance en Go.
DISK_GB = "disk_gb"
#: Sous-fournisseur réel (utile pour les agrégateurs, ex. Prime Intellect).
PROVIDER_DETAIL = "provider_detail"

#: Colonnes métier obligatoires — doivent toutes être présentes dans le frame.
COLUMNS: list[str] = [SNAPSHOTTED_AT, SOURCE, GPU_MODEL, LEASE_TYPE, PRICE, AVAILABILITY]

#: Colonnes descriptives optionnelles — backfillées si absentes (rétrocompat).
OPTIONAL_COLUMNS: list[str] = [REGION, GPU_MEMORY_GB, VCPU, RAM_GB, DISK_GB, PROVIDER_DETAIL]

#: Ensemble complet des colonnes du schéma enrichi (obligatoires + optionnelles).
ALL_COLUMNS: list[str] = COLUMNS + OPTIONAL_COLUMNS


def normalize_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Projette ``frame`` sur le schéma canonique et force ses dtypes.

    Les colonnes obligatoires (:data:`COLUMNS`) doivent être présentes ; les
    colonnes optionnelles (:data:`OPTIONAL_COLUMNS`) sont backfillées avec
    ``None``/``NaN`` si absentes — ce qui rend la fonction **rétrocompatible**
    avec les Parquet écrits avant l'enrichissement du schéma.

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
        Les colonnes optionnelles absentes sont ajoutées avec ``object`` dtype
        (valeur ``None``).

    Raises
    ------
    ValueError
        Si une colonne obligatoire manque, ou si ``snapshotted_at`` contient des
        instants naïfs (sans fuseau) — interdits (intégrité point-in-time).
    """
    missing = [c for c in COLUMNS if c not in frame.columns]
    if missing:
        raise ValueError(f"Colonnes manquantes pour le schéma cold store : {missing}.")

    # Sélectionne les colonnes obligatoires présentes + les optionnelles présentes.
    present_optional = [c for c in OPTIONAL_COLUMNS if c in frame.columns]
    out = frame.loc[:, COLUMNS + present_optional].copy()

    # Backfille les colonnes optionnelles absentes (rétrocompat Parquet legacy).
    for col in OPTIONAL_COLUMNS:
        if col not in out.columns:
            out[col] = None

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

    # Réordonne selon ALL_COLUMNS pour un schéma stable.
    return out[ALL_COLUMNS].reset_index(drop=True)
