"""Tests de la baseline climatologique ERCOT (L0 §7)."""

from __future__ import annotations

import pandas as pd

from ercot_baseline import ClimatologyBaseline


def test_fit_base_rate_per_hour_month() -> None:
    idx = pd.to_datetime(
        [
            "2024-01-01T18:00Z",
            "2024-01-02T18:00Z",
            "2024-01-03T18:00Z",
            "2024-01-04T18:00Z",
            "2024-01-01T06:00Z",
            "2024-01-02T06:00Z",
        ]
    )
    labels = pd.Series([True, True, False, False, False, False], index=idx)
    b = ClimatologyBaseline.fit(labels)
    assert b.rates[(18, 1)] == 0.5  # 2 spikes / 4 à 18h en janvier
    assert b.rates[(6, 1)] == 0.0
    assert b.global_rate == 2 / 6


def test_predict_uses_table_then_global_fallback() -> None:
    idx = pd.to_datetime(["2024-01-01T18:00Z", "2024-01-02T18:00Z", "2024-01-01T06:00Z"])
    labels = pd.Series([True, False, False], index=idx)
    b = ClimatologyBaseline.fit(labels)
    p = b.predict(pd.DatetimeIndex(["2024-01-09T18:00Z", "2024-06-09T12:00Z"], tz="UTC"))
    assert p[0] == 0.5  # (18, janvier) connu
    assert p[1] == b.global_rate  # (12, juin) inconnu → repli global
