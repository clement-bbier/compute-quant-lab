"""Anti look-ahead : une observation future n'entre jamais dans une mesure passée.

Tests **discriminants** : un bug de look-ahead (ignorer ``as_of``) changerait ``n_sources``
et la valeur de l'indice aux instants antérieurs — ils échoueraient alors.
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
            Snapshot(ago(5), "vastai", h, 2.00, availability=10),
            Snapshot(ago(5), "lambda", h, 2.10, availability=10),
            Snapshot(ago(1), "runpod", h, 1.90, availability=10),  # arrive APRÈS ago(3)
        ]
    )


def test_curve_excludes_observations_after_the_fix():
    store = _store_with_late_arrival()
    curve = price_curve(store, "H100", [ago(3), ago(0)])
    # À ago(3), runpod (daté ago(1)) n'existe pas encore : 2 venues, indice = 2.05.
    assert curve.loc[0, "n_sources"] == 2
    assert curve.loc[0, "index_price"] == pytest.approx(2.05)
    # À ago(0), les 3 venues sont visibles.
    assert curve.loc[1, "n_sources"] == 3


def test_read_market_cheapest_is_point_in_time():
    store = _store_with_late_arrival()
    # À ago(3), la moins chère est vastai (2.00) ; runpod (1.90) est encore dans le futur.
    early = read_market(store, ago(3), "H100")
    assert early.cheapest.source == "vastai"
    # À ago(0), runpod (1.90) devient la moins chère.
    late = read_market(store, ago(0), "H100")
    assert late.cheapest.source == "runpod"


def test_default_fixture_excludes_future_snapshot(store, as_of):
    # Le jeu calibré contient un relevé 'future' (as_of + 1 h) : jamais retenu à as_of.
    market = read_market(store, as_of, "H100")
    assert "future" not in {v.source for v in market.venues}
