"""(a) Round-trip Parquet : types, partition source/mois, préservation de la distribution."""

from __future__ import annotations

from typing import Callable, Sequence

import pandas as pd
import pytest

from core.storage import ParquetPriceStore
from core.storage.protocols import PriceStore
from core.storage.schema import AVAILABILITY, PRICE, SNAPSHOTTED_AT, SOURCE

Frame = Callable[[Sequence[tuple]], pd.DataFrame]


def test_store_satisfies_pricestore_protocol(store: ParquetPriceStore) -> None:
    assert isinstance(store, PriceStore)


def test_roundtrip_preserves_rows_and_types(store: ParquetPriceStore, make_frame: Frame) -> None:
    frame = make_frame([(0, "vastai", "H100", 2.50, 8), (0, "runpod", "H100", 2.10, 1)])

    store.write(frame)
    out = store.read()

    assert len(out) == 2
    assert str(out[SNAPSHOTTED_AT].dtype) == "datetime64[ns, UTC]"
    assert out[PRICE].dtype == "float64"
    assert out[AVAILABILITY].dtype == "int64"
    assert {(row[SOURCE], row[PRICE]) for _, row in out.iterrows()} == {
        ("vastai", 2.50),
        ("runpod", 2.10),
    }


def test_roundtrip_preserves_distribution(store: ParquetPriceStore, make_frame: Frame) -> None:
    # N offres pour le même (instant, source, modèle, bail) à prix distincts : le store
    # ne doit PAS les écraser à une ligne (le défaut de CsvSnapshotStore qu'on corrige).
    frame = make_frame(
        [
            (0, "vastai", "H100", 2.50, 8),
            (0, "vastai", "H100", 2.65, 4),
            (0, "vastai", "H100", 2.40, 2),
        ]
    )

    store.write(frame)
    out = store.read()

    assert len(out) == 3
    assert sorted(out[PRICE].tolist()) == [2.40, 2.50, 2.65]


def test_partition_layout_by_source_and_month(store: ParquetPriceStore, make_frame: Frame) -> None:
    frame = make_frame([(0, "vastai", "H100", 2.50, 8), (0, "runpod", "H100", 2.10, 1)])

    store.write(frame)

    dirs = {p.name for p in store.root.rglob("*") if p.is_dir()}
    assert "source=vastai" in dirs
    assert "source=runpod" in dirs
    assert "month=202501" in dirs


def test_write_rejects_naive_timestamps(store: ParquetPriceStore, make_frame: Frame) -> None:
    frame = make_frame([(0, "vastai", "H100", 2.50, 8)])
    frame[SNAPSHOTTED_AT] = frame[SNAPSHOTTED_AT].dt.tz_localize(None)  # casse l'intégrité UTC

    with pytest.raises(ValueError):
        store.write(frame)
