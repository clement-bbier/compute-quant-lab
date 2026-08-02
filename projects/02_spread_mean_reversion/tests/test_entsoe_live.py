"""ENTSO-E first-contact live smoke test (V5.2 campaign) -- real API, real token.

Minimal: 2-3 days of FR day-ahead prices via ``data_sources.load_energy_entsoe`` (P02's own
ENTSO-E path). Skipped when ``ENTSOE_API_TOKEN`` is absent; never run in CI (see the ``live``
marker in pyproject.toml).

Run: ``set -a && source .env && set +a && uv run pytest -m live projects/02_spread_mean_reversion -v``.
"""

from __future__ import annotations

import os

import pandas as pd
import pytest

from data_sources import load_energy_entsoe

REGION = "FR"


@pytest.mark.live
def test_entsoe_day_ahead_live() -> None:
    token = os.environ.get("ENTSOE_API_TOKEN")
    if not token:
        pytest.skip("ENTSOE_API_TOKEN is missing -- export the token for the live test")

    end = pd.Timestamp.now(tz="UTC").normalize()
    start = end - pd.Timedelta(days=3)

    series = load_energy_entsoe(REGION, start, end)

    assert len(series) > 0, "The ENTSO-E series is empty"

    index = pd.DatetimeIndex(series.index)
    assert index.tz is not None
    assert str(index.tz) == "UTC", f"Unexpected timezone: {index.tz}"
    assert index.is_monotonic_increasing, "The index is not sorted chronologically"

    assert not series.isna().any(), f"{series.isna().sum()} NaN values in the real series"

    # Plausible day-ahead range for FR (EUR/MWh): allow negative prices (real phenomenon,
    # high renewable output) but reject anything implausibly extreme.
    assert series.min() > -500.0, f"Abnormal minimum price: {series.min()}"
    assert series.max() < 5_000.0, f"Abnormal maximum price: {series.max()}"

    assert series.name == REGION
