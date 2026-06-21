"""(c) Point-in-time : ``read(as_of=t)`` ne renvoie que ``snapshotted_at <= t`` (anti look-ahead)."""

from __future__ import annotations

from typing import Callable, Sequence

import pandas as pd
import pytest

from core.storage import ParquetPriceStore
from core.storage.schema import SNAPSHOTTED_AT, SOURCE

Frame = Callable[[Sequence[tuple]], pd.DataFrame]


def _seed(store: ParquetPriceStore, make_frame: Frame) -> None:
    store.write(
        make_frame(
            [
                (0, "vastai", "H100", 2.50, 8),
                (1, "vastai", "H100", 2.55, 8),
                (2, "runpod", "H100", 2.20, 1),
            ]
        )
    )


def test_read_as_of_excludes_future_observations(
    store: ParquetPriceStore, make_frame: Frame, at: Callable[[int], pd.Timestamp]
) -> None:
    _seed(store, make_frame)

    out = store.read(as_of=at(1))

    assert len(out) == 2
    assert (out[SNAPSHOTTED_AT] <= at(1)).all()


def test_read_as_of_before_history_is_empty(
    store: ParquetPriceStore, make_frame: Frame, at: Callable[[int], pd.Timestamp]
) -> None:
    _seed(store, make_frame)

    assert store.read(as_of=at(-1)).empty


def test_read_without_as_of_returns_all(store: ParquetPriceStore, make_frame: Frame) -> None:
    _seed(store, make_frame)

    assert len(store.read()) == 3


def test_read_filters_by_source(store: ParquetPriceStore, make_frame: Frame) -> None:
    _seed(store, make_frame)

    out = store.read(source="runpod")

    assert len(out) == 1
    assert (out[SOURCE] == "runpod").all()


def test_read_rejects_naive_as_of(
    store: ParquetPriceStore, make_frame: Frame, at: Callable[[int], pd.Timestamp]
) -> None:
    _seed(store, make_frame)

    with pytest.raises(ValueError):
        store.read(as_of=at(1).tz_localize(None))
