"""Partitioned Parquet cold store (Phase 0 implementation of :class:`PriceStore`).

A columnar, typed, compressed price lake partitioned by ``source`` / month — append-only
and idempotent. This is the lab's **reproducibility foundation**: an immutable,
point-in-time history, plain-git-versioned, on which every model trains identically.

Idempotence by **full row content** (price included): rewriting the same reading is a
no-op, but distinct offers at the same instant/source/model are **all kept** — the store
remains a faithful journal of observations, aggregation (trimmed mean) staying the
responsibility of the P04 index.
"""

from __future__ import annotations

import datetime as dt
import uuid
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.dataset as pads

from core.storage.schema import (
    COLUMNS,
    INGESTED_AT,
    OPTIONAL_COLUMNS,
    SNAPSHOTTED_AT,
    SOURCE,
    normalize_frame,
)
from core.utils.logging import get_logger

logger = get_logger(__name__)

#: Monthly partition column derived from ``snapshotted_at`` (``YYYYMM``).
_MONTH = "month"
_PARTITIONING = pads.partitioning(
    pa.schema([(SOURCE, pa.string()), (_MONTH, pa.string())]), flavor="hive"
)

#: Dedup key: mandatory business columns (:data:`COLUMNS`) + the optional descriptive
#: columns (:data:`OPTIONAL_COLUMNS` -- region, provider_detail, ...). Two rows that agree
#: on every business/descriptive field are the same observation; two rows that differ in
#: region or provider_detail (even at the same instant/source/model/price) are genuinely
#: DISTINCT offers and must both be kept (module docstring: "faithful journal").
#: Deliberately excludes ``simulated``/``ingested_at`` (provenance, not payload) and
#: excludes nothing else -- a key narrower than this would silently drop real observations.
_DEDUP_KEY: list[str] = COLUMNS + OPTIONAL_COLUMNS


class ParquetPriceStore:
    """:class:`PriceStore` over a Parquet lake partitioned by ``source`` / month.

    Parameters
    ----------
    root
        Root of the lake (created if absent). Each partition lives under
        ``source=<src>/month=<YYYYMM>/``.
    """

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def write(self, frame: pd.DataFrame) -> int:
        """Append ``frame`` to the lake (typed, partitioned, deduplicated); returns new rows.

        ``ingested_at`` is stamped here, forward-only, at the instant of this write --
        never accepted from the caller's frame -- so it always reflects when the row
        actually entered the lake (as opposed to ``snapshotted_at``, when the price was
        observed). Deduplication (:data:`_DEDUP_KEY`) ignores it: replaying the same
        observation is still a no-op even though a hypothetical second write would stamp
        a different ``ingested_at``. The key includes the optional descriptive columns
        (region, provider_detail, ...): two rows at the same instant/source/model/price but
        a different region are DISTINCT offers, never collapsed into one (module docstring).
        """
        frame = normalize_frame(frame)
        if frame.empty:
            return 0
        # fillna: merge/drop_duplicates on a NaN-bearing key treats NaN != NaN (pandas
        # default), which would make every legacy row missing an optional column compare
        # as "distinct" from every other -- a dedup key must use a sentinel so two rows
        # that are both genuinely missing region (say) still collide as duplicates.
        key_frame = frame[_DEDUP_KEY].fillna("__NULL__")
        incoming = frame[~key_frame.duplicated()]  # intra-batch dedup
        n_intra_batch_dupes = len(frame) - len(incoming)
        existing = self.read()
        if not existing.empty:
            incoming_key = incoming[_DEDUP_KEY].fillna("__NULL__")
            existing_key = existing[_DEDUP_KEY].fillna("__NULL__").drop_duplicates()
            anti = incoming_key.reset_index(drop=True).merge(
                existing_key, on=_DEDUP_KEY, how="left", indicator=True
            )
            incoming = incoming[anti["_merge"].to_numpy() == "left_only"]
        n_dupes = len(frame) - n_intra_batch_dupes - len(incoming)
        if incoming.empty:
            logger.info(
                "ParquetPriceStore %s: 0 new row(s) written (%d already present)",
                self.root,
                n_dupes,
            )
            return 0
        part = incoming.copy()
        part[INGESTED_AT] = pd.Timestamp.now(tz="UTC")
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
        logger.info(
            "ParquetPriceStore %s: %d new row(s) written, %d deduplicated",
            self.root,
            len(part),
            n_dupes,
        )
        return len(part)

    def read(self, *, as_of: dt.datetime | None = None, source: str | None = None) -> pd.DataFrame:
        """Read the whole lake back as a typed canonical frame (order not guaranteed)."""
        if not any(self.root.rglob("*.parquet")):
            logger.warning("ParquetPriceStore %s: lake is empty, returning 0 rows", self.root)
            return normalize_frame(pd.DataFrame(columns=COLUMNS))
        # exclude_invalid_files: the lake can coexist with other files in the same root
        # (P04 CSV under dual writing) — only the store's Parquet files are read.
        dataset = pads.dataset(
            self.root, format="parquet", partitioning="hive", exclude_invalid_files=True
        )
        out = normalize_frame(dataset.to_table().to_pandas())
        if source is not None:
            out = out[out[SOURCE] == source]
        if as_of is not None:
            cutoff = pd.Timestamp(as_of)
            if cutoff.tzinfo is None:
                raise ValueError("as_of must be a tz-aware datetime (UTC), not naive.")
            out = out[out[SNAPSHOTTED_AT] <= cutoff.tz_convert("UTC")]
        return out.reset_index(drop=True)
