"""Cold store énergie (séries temporelles point-in-time) — Parquet partitionné.

Format **long** : ``(source, series, publish_time, interval_start, value)``. La colonne
``publish_time`` préserve le **point-in-time** des prévisions (load / capacité STSA /
net-load : connues à leur heure de publication) ; pour les séries *réalisées* (prix RTM),
``publish_time = interval_start`` (connu en fin d'intervalle).

Append-only, **idempotent au contenu**, partitionné ``series`` / mois — socle de
reproductibilité de la calibration (rule training-cold-store : l'entraînement lit ce lac
immuable versionné DVC, jamais du live). Parallèle au lac de prix GPU (``ParquetPriceStore``),
schéma distinct car l'énergie porte deux horodatages (publication + cible).
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.dataset as pads

#: Marché d'origine (``"ercot"``).
SOURCE = "source"
#: Série (``"rtm_spp"`` / ``"load_forecast"`` / ``"available_capacity"`` / ``"net_load_forecast"``).
SERIES = "series"
#: Heure de publication (UTC tz-aware) — clé du point-in-time des prévisions.
PUBLISH_TIME = "publish_time"
#: Heure cible de l'intervalle (UTC tz-aware).
INTERVAL_START = "interval_start"
#: Valeur observée ($/MWh pour RTM, MW pour charge/capacité/net-load).
VALUE = "value"

#: Colonnes obligatoires du schéma énergie.
COLUMNS: list[str] = [SOURCE, SERIES, PUBLISH_TIME, INTERVAL_START, VALUE]

_MONTH = "month"
_PARTITIONING = pads.partitioning(
    pa.schema([(SERIES, pa.string()), (_MONTH, pa.string())]), flavor="hive"
)


def normalize_energy_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Projette ``frame`` sur le schéma énergie et force les dtypes (horodatages UTC)."""
    missing = [c for c in COLUMNS if c not in frame.columns]
    if missing:
        raise ValueError(f"Colonnes manquantes pour le cold store énergie : {missing}.")
    out = frame.loc[:, COLUMNS].copy()
    for col in (PUBLISH_TIME, INTERVAL_START):
        ts = pd.to_datetime(out[col])
        if getattr(ts.dtype, "tz", None) is None:
            if ts.notna().any():
                raise ValueError(f"{col} naïf interdit : datetime tz-aware (UTC) requis.")
            ts = ts.dt.tz_localize("UTC")
        else:
            ts = ts.dt.tz_convert("UTC")
        out[col] = ts
    out[SOURCE] = out[SOURCE].astype(str)
    out[SERIES] = out[SERIES].astype(str)
    out[VALUE] = out[VALUE].astype("float64")
    return out.reset_index(drop=True)


class EnergyColdStore:
    """Lac Parquet énergie partitionné ``series`` / mois (point-in-time, idempotent).

    Parameters
    ----------
    root
        Racine du lac (créée si absente).
    """

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def write(self, frame: pd.DataFrame) -> int:
        """Append ``frame`` (typé, partitionné, dédupliqué) ; renvoie le nb de lignes neuves."""
        frame = normalize_energy_frame(frame)
        if frame.empty:
            return 0
        incoming = frame.drop_duplicates(subset=COLUMNS)
        existing = self.read()
        if not existing.empty:
            anti = incoming.merge(
                existing[COLUMNS].drop_duplicates(), on=COLUMNS, how="left", indicator=True
            )
            incoming = incoming[anti["_merge"].to_numpy() == "left_only"]
        if incoming.empty:
            return 0
        part = incoming.copy()
        part[_MONTH] = part[INTERVAL_START].dt.strftime("%Y%m")
        table = pa.Table.from_pandas(part, preserve_index=False)
        pads.write_dataset(
            table,
            self.root,
            format="parquet",
            partitioning=_PARTITIONING,
            existing_data_behavior="overwrite_or_ignore",
            basename_template=f"part-{uuid.uuid4().hex}-{{i}}.parquet",
        )
        return len(part)

    def read(self, *, series: str | None = None) -> pd.DataFrame:
        """Relit le lac (optionnellement filtré sur une ``series``) en frame typé."""
        if not any(self.root.rglob("*.parquet")):
            return normalize_energy_frame(pd.DataFrame(columns=COLUMNS))
        dataset = pads.dataset(
            self.root, format="parquet", partitioning="hive", exclude_invalid_files=True
        )
        out = normalize_energy_frame(dataset.to_table().to_pandas())
        if series is not None:
            out = out[out[SERIES] == series]
        return out.reset_index(drop=True)
