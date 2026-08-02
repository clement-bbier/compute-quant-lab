"""Anti look-ahead: a future observation never enters a past measurement.

**Discriminating** tests: a look-ahead bug (ignoring ``as_of``) would change ``n_sources``
and the index value at earlier instants — they would then fail.
"""

from __future__ import annotations

import pytest
from conftest import FakeSnapshotStore, ago

from core.ingestion.protocols import Snapshot
from views import price_curve, read_market


def _store_with_late_arrival() -> FakeSnapshotStore:
    h = "H100"
    return FakeSnapshotStore(
        [
            Snapshot(ago(5), "vastai", h, 2.00, availability=10, simulated=False),
            Snapshot(ago(5), "lambda", h, 2.10, availability=10, simulated=False),
            Snapshot(
                ago(1), "runpod", h, 1.90, availability=10, simulated=False
            ),  # arrives AFTER ago(3)
        ]
    )


def test_curve_excludes_observations_after_the_fix():
    store = _store_with_late_arrival()
    curve = price_curve(store, "H100", [ago(3), ago(0)])
    # At ago(3), runpod (dated ago(1)) doesn't exist yet: 2 venues, index = 2.05.
    assert curve.loc[0, "n_sources"] == 2
    assert curve.loc[0, "index_price"] == pytest.approx(2.05)
    # At ago(0), all 3 venues are visible.
    assert curve.loc[1, "n_sources"] == 3


def test_read_market_cheapest_is_point_in_time():
    store = _store_with_late_arrival()
    # At ago(3), the cheapest is vastai (2.00); runpod (1.90) is still in the future.
    early = read_market(store, ago(3), "H100")
    assert early.cheapest.source == "vastai"
    # At ago(0), runpod (1.90) becomes the cheapest.
    late = read_market(store, ago(0), "H100")
    assert late.cheapest.source == "runpod"


def test_default_fixture_excludes_future_snapshot(store, as_of):
    # The calibrated set contains a 'future' reading (as_of + 1 h): never retained at as_of.
    market = read_market(store, as_of, "H100")
    assert "future" not in {v.source for v in market.venues}
