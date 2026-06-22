"""(d) DuckDB : SQL embarqué (zéro serveur) sur le lac Parquet → résultats attendus."""

from __future__ import annotations

from typing import Callable, Sequence

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

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


def test_query_mixes_legacy_and_enriched_parquet(
    store: ParquetPriceStore, make_frame: Frame
) -> None:
    """Un parquet d'AVANT l'enrichissement (sans colonnes descriptives) cohabite avec un
    parquet enrichi : sélectionner une nouvelle colonne ne doit pas lever « schema mismatch »
    (union_by_name), la valeur manquante des vieux relevés étant NULL."""
    # Parquet legacy : seulement les colonnes métier historiques, écrit à la main dans la
    # partition Hive (source/month dérivés du chemin, comme les fichiers déjà dans le cloud).
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
    # Relevé enrichi via le store (normalize_frame ajoute les colonnes descriptives).
    store.write(make_frame([(1, "runpod", "H100", 2.20, 1)]))

    out = query("SELECT source, region FROM prices ORDER BY source", store)

    assert len(out) == 2
    assert (
        out["region"].isna().all()
    )  # aucune des deux sources n'a de région ici → NULL, pas d'erreur
