"""Tests des dislocations du basis : seuil (épisodes/amplitude) + demi-vie AR(1)."""

from __future__ import annotations

import pandas as pd
import pytest

from basis import DislocationSummary, detect_dislocations


def _hourly(values: list[float]) -> pd.Series:
    """Série basis horaire UTC à valeurs données."""
    idx = pd.date_range("2026-01-01", periods=len(values), freq="h", tz="UTC")
    return pd.Series(values, index=idx, name="basis_FR_DE")


def test_half_life_of_ar1_decay() -> None:
    """Décroissance AR(1) déterministe φ=0.5 → demi-vie = ln2/−ln0.5 = 1 heure."""
    phi = 0.5
    vals = [1.0]
    for _ in range(19):
        vals.append(phi * vals[-1])

    summary = detect_dislocations(_hourly(vals))

    assert isinstance(summary, DislocationSummary)
    assert summary.half_life_hours == pytest.approx(1.0, rel=1e-6)


def test_threshold_episodes_amplitude_and_fraction() -> None:
    """Seuil explicite = 2.0 : 2 épisodes contigus, 30 % du temps disloqué, p95 = 5.0."""
    vals = [0.0, 0.0, 0.0, 5.0, 5.0, 0.0, 0.0, 5.0, 0.0, 0.0]

    summary = detect_dislocations(_hourly(vals), threshold=2.0)

    assert summary.threshold == pytest.approx(2.0)
    assert summary.fraction_dislocated == pytest.approx(0.3)
    assert summary.n_dislocations == 2
    assert summary.amplitude_p95 == pytest.approx(5.0)


def test_non_mean_reverting_has_no_half_life() -> None:
    """Série explosive φ=1.05 (non mean-reverting) → demi-vie indéfinie (None)."""
    vals = [1.0]
    for _ in range(19):
        vals.append(1.05 * vals[-1])

    summary = detect_dislocations(_hourly(vals))

    assert summary.half_life_hours is None
