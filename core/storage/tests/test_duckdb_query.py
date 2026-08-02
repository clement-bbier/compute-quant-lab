"""DuckDB: embedded SQL (zero server) over the Parquet lake -> expected results."""

from __future__ import annotations

import logging
from typing import Callable, Sequence

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from core.storage import ParquetPriceStore
from core.storage.duckdb_query import query

Frame = Callable[[Sequence[tuple]], pd.DataFrame]


def _seed(store: ParquetPriceStore, make_frame: Frame) -> None:
    store.write(
        make_frame(
            [
                (0, "vastai", "H100", 2.50, 8),
                (1, "vastai", "H100", 2.70, 8),
                (2, "runpod", "H100", 2.20, 1),
            ]
        )
    )


def test_group_by_source_counts(store: ParquetPriceStore, make_frame: Frame) -> None:
    _seed(store, make_frame)

    out = query("SELECT source, COUNT(*) AS n FROM prices GROUP BY source ORDER BY source", store)

    assert dict(zip(out["source"], out["n"])) == {"runpod": 1, "vastai": 2}


def test_aggregate_price_for_one_source(store: ParquetPriceStore, make_frame: Frame) -> None:
    _seed(store, make_frame)

    out = query(
        "SELECT AVG(price_usd_per_hour) AS avg_px FROM prices WHERE source = 'vastai'", store
    )

    assert out["avg_px"].iloc[0] == 2.60


def test_query_on_empty_store_returns_empty(store: ParquetPriceStore) -> None:
    out = query("SELECT COUNT(*) AS n FROM prices", store)

    assert out["n"].iloc[0] == 0


def test_query_on_empty_store_logs_warning(
    store: ParquetPriceStore, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        query("SELECT COUNT(*) AS n FROM prices", store)

    assert "empty" in caplog.text.lower()


def test_query_mixes_legacy_and_enriched_parquet(
    store: ParquetPriceStore, make_frame: Frame
) -> None:
    """A Parquet file without the descriptive columns coexists with an enriched one:
    selecting a descriptive column must not raise "schema mismatch" (union_by_name), the
    missing value of the legacy readings being NULL."""
    # Legacy Parquet: only the historical business columns, written by hand into the Hive
    # partition (source/month derived from the path, like the files already in the cloud).
    legacy_part = store.root / "source=vastai" / "month=202501"
    legacy_part.mkdir(parents=True)
    legacy = pd.DataFrame(
        {
            "snapshotted_at": pd.to_datetime([pd.Timestamp("2025-01-01", tz="UTC")]),
            "gpu_model": ["H100"],
            "lease_type": ["on_demand"],
            "price_usd_per_hour": [2.50],
            "availability": [8],
        }
    )
    pq.write_table(
        pa.Table.from_pandas(legacy, preserve_index=False), legacy_part / "legacy.parquet"
    )
    # Enriched reading via the store (normalize_frame adds the descriptive columns).
    store.write(make_frame([(1, "runpod", "H100", 2.20, 1)]))

    out = query("SELECT source, region FROM prices ORDER BY source", store)

    assert len(out) == 2
    assert out["region"].isna().all()  # neither source has a region here -> NULL, no error
