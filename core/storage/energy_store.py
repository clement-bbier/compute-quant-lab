"""Energy cold store (point-in-time time series) — partitioned Parquet.

**Long** format: ``(source, series, publish_time, interval_start, value)``. The
``publish_time`` column preserves the **point-in-time** of forecasts (load / STSA
capacity / net-load: known at their publication time); for *realized* series (RTM
prices), ``publish_time = interval_start`` (known at the end of the interval).

ENTSO-E day-ahead prices (``source="entsoe_fr"`` / ``"entsoe_de"``, ``series="day_ahead_price"``,
written by ``infra.collectors.entsoe_backfill``) are neither: ``entsoe-py`` returns no
publication timestamp, so ``publish_time`` is an **approximated convention** — auction
results are published around **D-1 ~12:45 Europe/Paris** (CET/CEST), so
``publish_time = interval_start.floor("D") - 1 day`` at 12:45 local Paris time, converted
to UTC. This is documented here, in the backfill script, and in the P02/P05 docs so the
approximation is never mistaken for an API-confirmed timestamp.

Append-only, **content-idempotent**, partitioned by ``series`` / month — the foundation
of calibration reproducibility (training-cold-store rule: training reads this immutable
plain-git-versioned lake, never live data). Parallel to the GPU price lake
(``ParquetPriceStore``), with a distinct schema because energy carries two timestamps
(publication + target).

Point-in-time reads: ``read(as_of=...)`` filters on ``publish_time`` -- a row published
after ``as_of`` is excluded, so a backtest replaying instant ``t`` never sees a forecast
vintage that was not yet known at ``t``. ``as_of=None`` (default) returns everything
(full backward compatibility).

Provenance (``simulated``, ``ingested_at``): same tolerated-absent contract as the GPU
lake (``core.storage.schema``) -- every backfill collector wired today (ENTSO-E, ERCOT)
reads a real market, so ``simulated`` is always written ``False`` and a legacy row
missing the column is backfilled to ``False``, not rejected. ``ingested_at`` is stamped
forward-only at write time; legacy rows backfill to ``NaT`` (unknown ingestion time).
"""

from __future__ import annotations

import datetime as dt
import uuid
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.dataset as pads

from core.utils.logging import get_logger

logger = get_logger(__name__)

#: Originating market (``"ercot"``).
SOURCE = "source"
#: Series (``"rtm_spp"`` / ``"load_forecast"`` / ``"available_capacity"`` / ``"net_load_forecast"``).
SERIES = "series"
#: Publication time (UTC tz-aware) — key to the point-in-time of forecasts.
PUBLISH_TIME = "publish_time"
#: Target time of the interval (UTC tz-aware).
INTERVAL_START = "interval_start"
#: Observed value ($/MWh for RTM, MW for load/capacity/net-load).
VALUE = "value"
#: Real (``False``) vs simulated (``True``) provenance — tolerated-absent on legacy rows
#: (backfilled to ``False``; see module docstring).
SIMULATED = "simulated"
#: Instant the row entered the lake (UTC tz-aware) — forward-only, absent on legacy rows.
INGESTED_AT = "ingested_at"

#: Mandatory columns of the energy schema.
COLUMNS: list[str] = [SOURCE, SERIES, PUBLISH_TIME, INTERVAL_START, VALUE]

#: Provenance columns — tolerated-absent (see module docstring for backfill values).
PROVENANCE_COLUMNS: list[str] = [SIMULATED, INGESTED_AT]

_MONTH = "month"
_PARTITIONING = pads.partitioning(
    pa.schema([(SERIES, pa.string()), (_MONTH, pa.string())]), flavor="hive"
)


def normalize_energy_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Project ``frame`` onto the energy schema and enforce dtypes (UTC timestamps).

    ``simulated``/``ingested_at`` (:data:`PROVENANCE_COLUMNS`) are tolerated-absent, same
    contract as the GPU lake schema: backfilled to ``False``/``NaT`` when the input frame
    predates these columns (see module docstring for the provenance rationale).
    """
    missing = [c for c in COLUMNS if c not in frame.columns]
    if missing:
        raise ValueError(f"frame columns ({missing}) must be present for the energy cold store.")
    present_provenance = [c for c in PROVENANCE_COLUMNS if c in frame.columns]
    out = frame.loc[:, COLUMNS + present_provenance].copy()
    if SIMULATED not in out.columns:
        out[SIMULATED] = False
    if INGESTED_AT not in out.columns:
        out[INGESTED_AT] = pd.NaT
    for col in (PUBLISH_TIME, INTERVAL_START, INGESTED_AT):
        ts = pd.to_datetime(out[col])
        if getattr(ts.dtype, "tz", None) is None:
            if ts.notna().any():
                raise ValueError(f"{col} must be a tz-aware datetime (UTC), not naive.")
            ts = ts.dt.tz_localize("UTC")
        else:
            ts = ts.dt.tz_convert("UTC")
        out[col] = ts
    out[SOURCE] = out[SOURCE].astype(str)
    out[SERIES] = out[SERIES].astype(str)
    out[VALUE] = out[VALUE].astype("float64")
    out[SIMULATED] = out[SIMULATED].astype("bool")
    return out[COLUMNS + PROVENANCE_COLUMNS].reset_index(drop=True)


class EnergyColdStore:
    """Energy Parquet lake partitioned by ``series`` / month (point-in-time, idempotent).

    Parameters
    ----------
    root
        Root of the lake (created if absent).
    """

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def write(self, frame: pd.DataFrame) -> int:
        """Append ``frame`` (typed, partitioned, deduplicated); returns the number of new rows.

        ``ingested_at`` is stamped here, forward-only, at the instant of this write --
        never accepted from the caller's frame (mirrors ``ParquetPriceStore.write``).
        Deduplication (``COLUMNS`` only) ignores it.
        """
        frame = normalize_energy_frame(frame)
        if frame.empty:
            return 0
        incoming = frame.drop_duplicates(subset=COLUMNS)
        n_intra_batch_dupes = len(frame) - len(incoming)
        existing = self.read()
        if not existing.empty:
            anti = incoming.merge(
                existing[COLUMNS].drop_duplicates(), on=COLUMNS, how="left", indicator=True
            )
            incoming = incoming[anti["_merge"].to_numpy() == "left_only"]
        n_dupes = len(frame) - n_intra_batch_dupes - len(incoming)
        if incoming.empty:
            logger.info(
                "EnergyColdStore %s: 0 new row(s) written (%d already present)",
                self.root,
                n_dupes,
            )
            return 0
        part = incoming.copy()
        part[INGESTED_AT] = pd.Timestamp.now(tz="UTC")
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
        logger.info(
            "EnergyColdStore %s: %d new row(s) written, %d deduplicated",
            self.root,
            len(part),
            n_dupes,
        )
        return len(part)

    def read(
        self,
        *,
        series: str | None = None,
        as_of: pd.Timestamp | dt.datetime | None = None,
    ) -> pd.DataFrame:
        """Read the lake back (optionally filtered on ``series``/``as_of``) as a typed frame.

        Parameters
        ----------
        series
            Keep only this series when given.
        as_of
            Point-in-time cutoff (UTC tz-aware): a row **published after** ``as_of``
            (``publish_time > as_of``) is excluded -- it was not yet known at that
            instant. ``None`` (default) returns every row regardless of publication time
            (full backward compatibility). The boundary is inclusive: a row with
            ``publish_time == as_of`` is kept.
        """
        if not any(self.root.rglob("*.parquet")):
            logger.warning("EnergyColdStore %s: lake is empty, returning 0 rows", self.root)
            return normalize_energy_frame(pd.DataFrame(columns=COLUMNS))
        dataset = pads.dataset(
            self.root, format="parquet", partitioning="hive", exclude_invalid_files=True
        )
        out = normalize_energy_frame(dataset.to_table().to_pandas())
        if series is not None:
            out = out[out[SERIES] == series]
        if as_of is not None:
            cutoff = pd.Timestamp(as_of)
            if cutoff.tzinfo is None:
                raise ValueError("as_of must be a tz-aware datetime (UTC), not naive.")
            out = out[out[PUBLISH_TIME] <= cutoff.tz_convert("UTC")]
        return out.reset_index(drop=True)
