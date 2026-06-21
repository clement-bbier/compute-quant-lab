"""(d) DuckDB : SQL embarqué (zéro serveur) sur le lac Parquet → résultats attendus."""

from __future__ import annotations

from typing import Callable, Sequence

import pandas as pd

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
