"""Idempotence: re-appending the same reading never creates a duplicate.

Guarantees that a replayable scheduled collector (same instant recorded twice) does not
introduce duplicates, while keeping the genuinely distinct offers (distribution).
"""

from __future__ import annotations

from typing import Callable, Sequence

import pandas as pd

from core.storage import ParquetPriceStore
from core.storage.schema import PRICE

Frame = Callable[[Sequence[tuple]], pd.DataFrame]


def test_rewriting_same_batch_is_noop(store: ParquetPriceStore, make_frame: Frame) -> None:
    frame = make_frame([(0, "vastai", "H100", 2.50, 8), (0, "runpod", "H100", 2.10, 1)])

    first = store.write(frame)
    second = store.write(frame)

    assert first == 2
    assert second == 0  # nothing new
    assert len(store.read()) == 2


def test_partial_overlap_writes_only_new_rows(store: ParquetPriceStore, make_frame: Frame) -> None:
    batch_a = make_frame([(0, "vastai", "H100", 2.50, 8)])
    batch_ab = make_frame([(0, "vastai", "H100", 2.50, 8), (1, "vastai", "H100", 2.55, 8)])

    store.write(batch_a)
    new_rows = store.write(batch_ab)

    assert new_rows == 1  # only the 2nd row is new
    out = store.read()
    assert len(out) == 2
    assert sorted(out[PRICE].tolist()) == [2.50, 2.55]


def test_distinct_offers_same_key_are_not_deduplicated(
    store: ParquetPriceStore, make_frame: Frame
) -> None:
    # Same (instant, source, model, lease) but distinct price/availability => distinct rows.
    frame = make_frame([(0, "vastai", "H100", 2.50, 8), (0, "vastai", "H100", 2.65, 4)])

    store.write(frame)
    store.write(frame)  # replayed: still no duplicate, but 2 offers kept

    assert len(store.read()) == 2
