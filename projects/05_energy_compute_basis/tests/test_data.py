"""Tests for P05 I/O: deterministic synthetic fallback + source labeling."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from data import hourly_index, load_compute_index, load_regional_energy


def test_regional_energy_synthetic_is_deterministic_and_utc() -> None:
    """Offline (allow_remote=False), energy is synthetic, labeled, deterministic."""
    idx = hourly_index("2025-01-01", 48)

    df1, label1 = load_regional_energy(idx, ["FR", "DE"], allow_remote=False)
    df2, label2 = load_regional_energy(idx, ["FR", "DE"], allow_remote=False)

    assert label1 == "synthetic" and label2 == "synthetic"
    assert list(df1.columns) == ["FR", "DE"]
    assert str(df1.index.tz) == "UTC"
    assert (df1 > 0).to_numpy().all()
    pd.testing.assert_frame_equal(df1, df2)
    # FR and DE must be two distinct series (otherwise basis identically zero at equal PUE).
    assert not df1["FR"].equals(df1["DE"])


def test_compute_index_synthetic_fallback(tmp_path: Path) -> None:
    """Without real snapshots, the compute index falls back to labeled synthetic (1 global column)."""
    idx = hourly_index("2025-01-01", 48)

    df, label = load_compute_index(idx, "H100", snapshot_dir=tmp_path)

    assert label == "synthetic"
    assert list(df.columns) == ["H100"]
    assert str(df.index.tz) == "UTC"
    assert (df["H100"] > 0).all()
