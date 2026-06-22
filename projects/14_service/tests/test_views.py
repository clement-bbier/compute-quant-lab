"""Tests de la couche vue (mesure publique : lecture du cold store)."""

from __future__ import annotations


import pytest
from conftest import ago

from core.ingestion.compute_index import InsufficientDataError
from views import MarketView, price_curve, read_market


def test_read_market_designates_cheapest_kept_venue(store, as_of):
    market = read_market(store, as_of, "H100")
    # La venue scam (0.05) est un outlier rejeté : la moins chère RETENUE est vastai.
    assert market.cheapest.source == "vastai"
    assert market.cheapest.rate == pytest.approx(2.00)


def test_read_market_canonical_index_price(store, as_of):
    market = read_market(store, as_of, "H100")
    # Indice canonique (trimmed mean 20 % + MAD 2.5) sur les 4 venues retenues.
    assert market.index_price == pytest.approx(2.15)


def test_read_market_ranks_venues_ascending(store, as_of):
    market = read_market(store, as_of, "H100")
    rates = [v.rate for v in market.venues]
    assert rates == sorted(rates)
    # scam/old/aws/future écartés : seules les 4 venues fraîches valides restent.
    assert {v.source for v in market.venues} == {"vastai", "lambda", "runpod", "coreweave"}


def test_read_market_raises_on_empty_lake(empty_store, as_of):
    with pytest.raises(InsufficientDataError):
        read_market(empty_store, as_of, "H100")


def test_market_view_rejects_empty_venues(as_of):
    with pytest.raises(ValueError):
        MarketView(as_of=as_of, gpu_model="H100", venues=(), index_price=2.0, method="x")


def test_price_curve_returns_point_per_timestamp(store):
    timestamps = [ago(3), ago(1), ago(0)]
    curve = price_curve(store, "H100", timestamps)
    assert list(curve["as_of"]) == [ago(3), ago(1), ago(0)]
    assert (curve["index_price"] > 0).all()


def test_price_curve_degrades_to_nan_when_no_data(empty_store, as_of):
    curve = price_curve(empty_store, "H100", [as_of])
    assert curve.loc[0, "n_sources"] == 0
    assert curve.loc[0, "index_price"] != curve.loc[0, "index_price"]  # NaN
