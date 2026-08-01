"""DuckDB query layer (Phase 1): embedded analytical SQL over the Parquet lake.

DuckDB reads the partitioned Parquet **directly in SQL**, in process, with **zero
server** — ideal for EDA, point-in-time joins at scale and feature building (P07/P09).
Near-zero cost: no database to administer is introduced as long as the data stays batch
(see roadmap section 3 Phase 1, section 4 anti-over-engineering).

The query runs against a ``prices`` view exposing the canonical schema
(:data:`~core.storage.schema.COLUMNS` columns + the ``month`` partition). Since the
plain-git-versioned lake is immutable, replaying the same query at the same git SHA is
reproducible.
"""

from __future__ import annotations

import duckdb
import pandas as pd

from core.storage.parquet_store import ParquetPriceStore

#: DuckDB schema of the empty view (cold lake) — aligned on the enriched cold store + partition.
_EMPTY_VIEW_SCHEMA = (
    "snapshotted_at TIMESTAMP WITH TIME ZONE, source VARCHAR, gpu_model VARCHAR, "
    "lease_type VARCHAR, price_usd_per_hour DOUBLE, availability BIGINT, "
    "region VARCHAR, gpu_memory_gb DOUBLE, vcpu BIGINT, ram_gb DOUBLE, disk_gb DOUBLE, "
    "provider_detail VARCHAR, month VARCHAR"
)


def query(sql: str, store: ParquetPriceStore, *, view: str = "prices") -> pd.DataFrame:
    """Execute ``sql`` against the Parquet lake of ``store``, exposed as the ``view`` view.

    Parameters
    ----------
    sql
        DuckDB SQL query referencing the ``view`` view (default ``prices``).
    store
        The cold store whose Parquet root is queried.
    view
        Name of the view exposing the lake (default ``prices``).

    Returns
    -------
    pandas.DataFrame
        The result of the query. On an empty lake, the view has the right schema but
        0 rows (queries stay replayable even when cold).
    """
    con = duckdb.connect()
    try:
        files = sorted(store.root.rglob("*.parquet"))
        if files:
            # CREATE VIEW does not accept a prepared parameter: the glob (controlled
            # internal path) is inlined as POSIX, single quote escaped for safety.
            glob = (store.root / "**" / "*.parquet").as_posix().replace("'", "''")
            # union_by_name: the lake is heterogeneous (Parquet files from before the
            # schema enrichment, without the descriptive columns). Without union by NAME,
            # DuckDB reads by position and raises "schema mismatch in glob" as soon as a
            # column absent from the old files is selected; with it, missing columns are
            # NULL-filled.
            con.execute(
                f"CREATE VIEW {view} AS SELECT * FROM read_parquet("
                f"'{glob}', hive_partitioning => true, union_by_name => true)"
            )
        else:
            con.execute(f"CREATE TABLE {view} ({_EMPTY_VIEW_SCHEMA})")
        return con.execute(sql).fetchdf()
    finally:
        con.close()
