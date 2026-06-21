"""Tests des loaders de données : intégration P01 (pricing) et jambe compute réelle (ingestion).

``load_energy_entsoe`` (réseau ENTSO-E) n'est pas testé en unitaire (I/O token-gated, comme le
connecteur Vast.ai de P04). On teste ici le câblage *pur* : pricing du spread via P01 et
construction d'une série d'indice compute à partir de snapshots réels accumulés.
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
    # spread = revenu − coût (décomposition P01), franchement positif pour un H100.
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
