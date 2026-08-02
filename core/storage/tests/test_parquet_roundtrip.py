"""Parquet round-trip: types, source/month partition, preservation of the distribution."""

from __future__ import annotations

import logging
from typing import Callable, Sequence

import pandas as pd
import pytest

from core.storage import ParquetPriceStore
from core.storage.protocols import PriceStore
from core.storage.schema import AVAILABILITY, INGESTED_AT, PRICE, SIMULATED, SNAPSHOTTED_AT, SOURCE

Frame = Callable[[Sequence[tuple]], pd.DataFrame]


def test_read_empty_lake_logs_warning(
    store: ParquetPriceStore, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        out = store.read()
    assert out.empty
    assert "empty" in caplog.text.lower()


def test_write_logs_new_rows_and_dedup_count(
    store: ParquetPriceStore, make_frame: Frame, caplog: pytest.LogCaptureFixture
) -> None:
    frame = make_frame([(0, "vastai", "H100", 2.50, 8), (0, "runpod", "H100", 2.10, 1)])
    with caplog.at_level(logging.INFO):
        store.write(frame)
    assert "2 new row" in caplog.text

    caplog.clear()
    with caplog.at_level(logging.INFO):
        store.write(frame)  # re-writing the same rows: all deduplicated
    assert "0 new row" in caplog.text
    assert "2 already present" in caplog.text


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
    # N offers for the same (instant, source, model, lease) at distinct prices: the store
    # must NOT collapse them into one row (unlike the CsvSnapshotStore).
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
    frame[SNAPSHOTTED_AT] = frame[SNAPSHOTTED_AT].dt.tz_localize(None)  # breaks UTC integrity

    with pytest.raises(ValueError):
        store.write(frame)


def test_write_stamps_ingested_at_forward_only(store: ParquetPriceStore, make_frame: Frame) -> None:
    """`ingested_at` reflects the write, never accepted from the caller's frame."""
    frame = make_frame([(0, "vastai", "H100", 2.50, 8)])
    frame[INGESTED_AT] = pd.Timestamp("2020-01-01", tz="UTC")  # caller-supplied value: ignored

    store.write(frame)
    out = store.read()

    assert out[INGESTED_AT].notna().all()
    assert (out[INGESTED_AT] > pd.Timestamp("2020-01-01", tz="UTC")).all()
    assert str(out[INGESTED_AT].dtype).startswith("datetime64[") and str(
        out[INGESTED_AT].dtype
    ).endswith(", UTC]")


def test_write_backfills_simulated_false_for_legacy_frame(
    store: ParquetPriceStore, make_frame: Frame
) -> None:
    """`make_frame` yields only the mandatory COLUMNS: `simulated` is absent from the input."""
    frame = make_frame([(0, "vastai", "H100", 2.50, 8)])
    assert SIMULATED not in frame.columns

    store.write(frame)
    out = store.read()

    assert bool(out[SIMULATED].iloc[0]) is False
