"""Tests de l'I/O P05 : repli synthétique déterministe + étiquetage des sources."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from data import hourly_index, load_compute_index, load_regional_energy


def test_regional_energy_synthetic_is_deterministic_and_utc() -> None:
    """Hors réseau (allow_remote=False), l'énergie est synthétique, étiquetée, déterministe."""
    idx = hourly_index("2025-01-01", 48)

    df1, label1 = load_regional_energy(idx, ["FR", "DE"], allow_remote=False)
    df2, label2 = load_regional_energy(idx, ["FR", "DE"], allow_remote=False)

    assert label1 == "synthetic" and label2 == "synthetic"
    assert list(df1.columns) == ["FR", "DE"]
    assert str(df1.index.tz) == "UTC"
    assert (df1 > 0).to_numpy().all()
    pd.testing.assert_frame_equal(df1, df2)
    # FR et DE doivent être deux séries distinctes (sinon basis identiquement nul à PUE égal).
    assert not df1["FR"].equals(df1["DE"])


def test_compute_index_synthetic_fallback(tmp_path: Path) -> None:
    """Sans snapshots réels, l'indice compute bascule en synthétique étiqueté (1 colonne globale)."""
    idx = hourly_index("2025-01-01", 48)

    df, label = load_compute_index(idx, "H100", snapshot_dir=tmp_path)

    assert label == "synthetic"
    assert list(df.columns) == ["H100"]
    assert str(df.index.tz) == "UTC"
    assert (df["H100"] > 0).all()
