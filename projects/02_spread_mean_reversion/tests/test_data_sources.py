"""Tests for the data loaders: P01 (pricing) integration and the real compute leg (ingestion).

``load_energy_entsoe`` (ENTSO-E network call) is not unit-tested (I/O token-gated, like P04's
Vast.ai connector). Here we test the *pure* wiring: spread pricing via P01 and
building a compute index series from accumulated real snapshots.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from core.ingestion import Snapshot

from data_sources import DataProvenance, build_spread, compute_index_series


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
