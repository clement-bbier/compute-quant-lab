"""Tests for P05 I/O: cold store, deterministic synthetic fallback, source labeling."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from core.storage.energy_store import (
    INTERVAL_START,
    PUBLISH_TIME,
    SERIES,
    SOURCE,
    VALUE,
    EnergyColdStore,
)

from data import hourly_index, load_compute_index, load_regional_energy


def test_regional_energy_synthetic_is_deterministic_and_utc(tmp_path: Path) -> None:
    """Offline (allow_remote=False) and empty cold store, energy is synthetic, labeled, deterministic."""
    idx = hourly_index("2025-01-01", 48)
    empty_store = EnergyColdStore(tmp_path)

    df1, label1 = load_regional_energy(idx, ["FR", "DE"], allow_remote=False, store=empty_store)
    df2, label2 = load_regional_energy(idx, ["FR", "DE"], allow_remote=False, store=empty_store)

    assert label1 == "synthetic" and label2 == "synthetic"
    assert list(df1.columns) == ["FR", "DE"]
    assert str(df1.index.tz) == "UTC"
    assert (df1 > 0).to_numpy().all()
    pd.testing.assert_frame_equal(df1, df2)
    # FR and DE must be two distinct series (otherwise basis identically zero at equal PUE).
    assert not df1["FR"].equals(df1["DE"])


def test_regional_energy_reads_cold_store_when_present(tmp_path: Path) -> None:
    """Cold store with both regions covering the range wins over synthetic."""
    idx = hourly_index("2025-01-01", 4)
    store = EnergyColdStore(tmp_path)
    rows = []
    for region, source in (("FR", "entsoe_fr"), ("DE", "entsoe_de")):
        rows.append(
            pd.DataFrame(
                {
                    SOURCE: source,
                    SERIES: "day_ahead_price",
                    PUBLISH_TIME: idx - pd.Timedelta(days=1),
                    INTERVAL_START: idx,
                    VALUE: [40.0, 41.0, 42.0, 43.0] if region == "FR" else [30.0, 31.0, 32.0, 33.0],
                }
            )
        )
    store.write(pd.concat(rows, ignore_index=True))

    df, label = load_regional_energy(idx, ["FR", "DE"], allow_remote=False, store=store)

    assert label == "entsoe_cold_store"
    assert list(df["FR"].to_numpy()) == [40.0, 41.0, 42.0, 43.0]
    assert list(df["DE"].to_numpy()) == [30.0, 31.0, 32.0, 33.0]


def test_regional_energy_falls_back_when_cold_store_missing_one_region(tmp_path: Path) -> None:
    """A partial cold store (only FR) must not be mixed with synthetic DE: falls back fully."""
    idx = hourly_index("2025-01-01", 4)
    store = EnergyColdStore(tmp_path)
    store.write(
        pd.DataFrame(
            {
                SOURCE: "entsoe_fr",
                SERIES: "day_ahead_price",
                PUBLISH_TIME: idx - pd.Timedelta(days=1),
                INTERVAL_START: idx,
                VALUE: [40.0, 41.0, 42.0, 43.0],
            }
        )
    )

    df, label = load_regional_energy(idx, ["FR", "DE"], allow_remote=False, store=store)

    assert label == "synthetic"


def test_compute_index_synthetic_fallback(tmp_path: Path) -> None:
    """Without real snapshots, the compute index falls back to labeled synthetic (1 global column)."""
    idx = hourly_index("2025-01-01", 48)

    df, label = load_compute_index(idx, "H100", snapshot_dir=tmp_path)

    assert label == "synthetic"
    assert list(df.columns) == ["H100"]
    assert str(df.index.tz) == "UTC"
    assert (df["H100"] > 0).all()
