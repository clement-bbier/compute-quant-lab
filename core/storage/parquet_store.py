"""Cold store Parquet partitionné (implémentation Phase 0 de :class:`PriceStore`).

Lac de prix colonne, typé, compressé, partitionné ``source`` / mois — append-only et
idempotent. C'est le **socle de reproductibilité** du labo : un historique immuable et
point-in-time, versionné DVC, sur lequel tous les modèles s'entraînent à l'identique.

Idempotence par **contenu de ligne complet** (prix inclus) : ré-écrire un même relevé
est un no-op, mais des offres distinctes au même instant/source/modèle sont **toutes
conservées** — le store reste un journal d'observations fidèle, l'agrégation (trimmed
mean) restant la responsabilité de l'indice P04.
"""

from __future__ import annotations

import datetime as dt
import uuid
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.dataset as pads

from core.storage.schema import COLUMNS, SNAPSHOTTED_AT, SOURCE, normalize_frame

#: Colonne de partition mensuelle dérivée de ``snapshotted_at`` (``YYYYMM``).
_MONTH = "month"
_PARTITIONING = pads.partitioning(
    pa.schema([(SOURCE, pa.string()), (_MONTH, pa.string())]), flavor="hive"
)


class ParquetPriceStore:
    """:class:`PriceStore` sur un lac Parquet partitionné ``source`` / mois.

    Parameters
    ----------
    root
        Racine du lac (créée si absente). Chaque partition vit sous
        ``source=<src>/month=<YYYYMM>/``.
    """

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def write(self, frame: pd.DataFrame) -> int:
        """Append ``frame`` au lac (typé, partitionné, dédupliqué) ; renvoie le nb de lignes neuves."""
        frame = normalize_frame(frame)
        if frame.empty:
            return 0
        incoming = frame.drop_duplicates(subset=COLUMNS)  # dédup intra-batch
        existing = self.read()
        if not existing.empty:
            anti = incoming.merge(
                existing[COLUMNS].drop_duplicates(), on=COLUMNS, how="left", indicator=True
            )
            incoming = incoming[anti["_merge"].to_numpy() == "left_only"]
        if incoming.empty:
            return 0
        part = incoming.copy()
        part[_MONTH] = part[SNAPSHOTTED_AT].dt.strftime("%Y%m")
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

    def read(self, *, as_of: dt.datetime | None = None, source: str | None = None) -> pd.DataFrame:
        """Relit le lac entier en frame canonique typé (ordre non garanti)."""
        if not any(self.root.rglob("*.parquet")):
            return normalize_frame(pd.DataFrame(columns=COLUMNS))
        # exclude_invalid_files : le lac peut cohabiter avec d'autres fichiers dans la
        # même racine (CSV P04 en double écriture) — on ne lit que les Parquet du store.
        dataset = pads.dataset(
            self.root, format="parquet", partitioning="hive", exclude_invalid_files=True
        )
        out = normalize_frame(dataset.to_table().to_pandas())
        if source is not None:
            out = out[out[SOURCE] == source]
        if as_of is not None:
            cutoff = pd.Timestamp(as_of)
            if cutoff.tzinfo is None:
                raise ValueError("as_of naïf interdit : fournir un datetime tz-aware (UTC).")
            out = out[out[SNAPSHOTTED_AT] <= cutoff.tz_convert("UTC")]
        return out.reset_index(drop=True)
