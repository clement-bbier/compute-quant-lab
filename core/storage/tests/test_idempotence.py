"""(b) Idempotence : ré-appender un même relevé ne crée jamais de doublon.

Garantit qu'un collecteur planifié rejouable (même instant relevé deux fois) n'introduit
pas de duplicata, tout en conservant les offres réellement distinctes (distribution).
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
    assert second == 0  # rien de neuf
    assert len(store.read()) == 2


def test_partial_overlap_writes_only_new_rows(store: ParquetPriceStore, make_frame: Frame) -> None:
    batch_a = make_frame([(0, "vastai", "H100", 2.50, 8)])
    batch_ab = make_frame([(0, "vastai", "H100", 2.50, 8), (1, "vastai", "H100", 2.55, 8)])

    store.write(batch_a)
    new_rows = store.write(batch_ab)

    assert new_rows == 1  # seule la 2e ligne est neuve
    out = store.read()
    assert len(out) == 2
    assert sorted(out[PRICE].tolist()) == [2.50, 2.55]


def test_distinct_offers_same_key_are_not_deduplicated(
    store: ParquetPriceStore, make_frame: Frame
) -> None:
    # Même (instant, source, modèle, bail) mais prix/dispo distincts => lignes distinctes.
    frame = make_frame([(0, "vastai", "H100", 2.50, 8), (0, "vastai", "H100", 2.65, 4)])

    store.write(frame)
    store.write(frame)  # rejoué : toujours pas de doublon, mais 2 offres conservées

    assert len(store.read()) == 2
