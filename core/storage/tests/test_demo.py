"""Run consommateur : statistiques du cold store via DuckDB (logique pure, sans MLflow)."""

from __future__ import annotations

from typing import Callable, Sequence

import pandas as pd

from core.storage import ParquetPriceStore
from core.storage.demo import summarize

Frame = Callable[[Sequence[tuple]], pd.DataFrame]


def test_summarize_seeded_store(store: ParquetPriceStore, make_frame: Frame) -> None:
    store.write(
        make_frame(
            [
                (0, "vastai", "H100", 2.50, 8),
                (1, "vastai", "A100", 1.20, 8),
                (2, "runpod", "H100", 2.20, 1),
            ]
        )
    )

    summary = summarize(store)

    assert summary["n_rows"] == 3
    assert summary["n_sources"] == 2
    assert summary["n_models"] == 2


def test_summarize_empty_store(store: ParquetPriceStore) -> None:
    summary = summarize(store)

    assert summary["n_rows"] == 0
    assert summary["n_sources"] == 0
