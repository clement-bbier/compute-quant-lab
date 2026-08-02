"""Tests for the data loaders: P01 (pricing) integration and the real compute leg (ingestion).

``load_energy_entsoe``'s live ``entsoe-py`` path is not unit-tested (I/O token-gated, like
P04's Vast.ai connector) -- see ``test_entsoe_live.py``. Its cold-store path *is* unit-tested
here (deterministic, no network). We also test the *pure* wiring: spread pricing via P01 and
building a compute index series from accumulated real snapshots.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from core.ingestion import Snapshot
from core.storage.energy_store import (
    INTERVAL_START,
    PUBLISH_TIME,
    SERIES,
    SOURCE,
    VALUE,
    EnergyColdStore,
)

from data_sources import DataProvenance, build_spread, compute_index_series, load_energy_entsoe


def _utc(n: int) -> pd.DatetimeIndex:
    return pd.date_range("2025-01-01", periods=n, freq="h", tz="UTC")


def test_build_spread_decomposes_via_p01() -> None:
    idx = _utc(5)
    energy = pd.DataFrame({"FR": [150.0] * 5}, index=idx)
    compute = pd.DataFrame({"H100": [2.5] * 5}, index=idx)
    ds = build_spread(
        energy,
        compute,
        gpu="H100",
        region="FR",
        provenance=DataProvenance(source="test", simulated=True),
    )
    # spread = revenue - cost (P01 decomposition), clearly positive for an H100.
    np.testing.assert_allclose(
        ds.spread.to_numpy(), (ds.pricing.revenue - ds.pricing.cost).to_numpy()
    )
    assert (ds.spread.to_numpy() > 0).all()
    assert ds.provenance.simulated is True


def test_compute_index_series_from_real_snapshots() -> None:
    grid = _utc(3)
    snaps: list[Snapshot] = []
    for ts in grid:
        t = ts.to_pydatetime()
        snaps.append(Snapshot(t, "vastai", "H100", 2.0, availability=10))
        snaps.append(Snapshot(t, "runpod", "H100", 2.1, availability=8))
    series = compute_index_series(snaps, grid, "H100")
    assert len(series) == 3
    values = series.to_numpy()
    assert (values > 1.5).all() and (values < 2.5).all()


def test_compute_index_series_omits_grid_points_without_fresh_snapshot() -> None:
    """A grid point past the staleness window (default 24h) must be dropped, not carried forward."""
    grid = pd.DatetimeIndex(
        [pd.Timestamp("2025-01-01", tz="UTC"), pd.Timestamp("2025-01-05", tz="UTC")]
    )
    only_first = grid[0].to_pydatetime()
    snaps = [
        Snapshot(only_first, "vastai", "H100", 2.0, availability=10),
        Snapshot(only_first, "runpod", "H100", 2.1, availability=8),
    ]
    series = compute_index_series(snaps, grid, "H100")
    # The second fix is 4 days past the only snapshot (> 24h staleness): omitted, not NaN-filled.
    assert list(series.index) == [grid[0]]
    assert len(series) == 1


def test_load_energy_entsoe_reads_cold_store_when_present(tmp_path) -> None:
    store = EnergyColdStore(tmp_path)
    idx = _utc(3)
    store.write(
        pd.DataFrame(
            {
                SOURCE: "entsoe_fr",
                SERIES: "day_ahead_price",
                PUBLISH_TIME: idx - pd.Timedelta(days=1),
                INTERVAL_START: idx,
                VALUE: [40.0, 41.0, 42.0],
            }
        )
    )
    series, source = load_energy_entsoe(
        "FR", idx[0], idx[-1], store=store, token="unused-should-not-be-needed"
    )
    assert source == "entsoe_cold_store"
    assert list(series.to_numpy()) == [40.0, 41.0, 42.0]
    assert str(pd.DatetimeIndex(series.index).tz) == "UTC"
    assert series.name == "FR"


def test_load_energy_entsoe_raises_without_store_data_or_token(tmp_path) -> None:
    empty_store = EnergyColdStore(tmp_path)
    idx = _utc(3)
    with pytest.raises(RuntimeError, match="ENTSOE_API_TOKEN"):
        load_energy_entsoe("FR", idx[0], idx[-1], store=empty_store, token=None)
