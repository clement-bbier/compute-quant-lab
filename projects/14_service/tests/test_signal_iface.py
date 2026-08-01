"""Tests for the public/edge boundary: signal contract + naive public impl."""

from __future__ import annotations

import statistics

import pytest
from conftest import AS_OF

from core.ingestion.protocols import VenueRate
from signal_iface import (
    Action,
    NaiveSignalSource,
    SignalProvenance,
    SignalSource,
)
from views import MarketView


def _market(rates: list[float], *, model: str = "H100") -> MarketView:
    venues = tuple(
        sorted(
            (
                VenueRate(source=f"venue{i}", rate=r, availability=1, snapshotted_at=AS_OF)
                for i, r in enumerate(rates)
            ),
            key=lambda v: v.rate,
        )
    )
    return MarketView(
        as_of=AS_OF,
        gpu_model=model,
        venues=venues,
        index_price=statistics.mean(rates),
        method="test",
    )


def test_naive_rent_now_when_cheapest_below_median():
    source = NaiveSignalSource()
    signal = source.assess(_market([2.00, 2.20, 2.30]))
    assert signal.action is Action.RENT_NOW
    assert signal.venue == "venue0"  # the cheapest (2.00)
    assert signal.reference_price == pytest.approx(2.00)


def test_naive_waits_when_no_spread_single_venue():
    source = NaiveSignalSource()
    signal = source.assess(_market([2.00]))  # cheapest == median -> no gap
    assert signal.action is Action.WAIT


def test_naive_waits_when_all_venues_equal():
    source = NaiveSignalSource()
    signal = source.assess(_market([2.10, 2.10, 2.10]))
    assert signal.action is Action.WAIT


def test_naive_signal_is_flagged_non_edge():
    # The public free tier is NEVER a calibrated signal: simulated=True.
    signal = NaiveSignalSource().assess(_market([2.00, 2.20]))
    assert signal.provenance.simulated is True
    assert signal.provenance.name == "naive_public"


def test_provenance_flag_is_mandatory():
    # Rule forward-real-simulated: the flag has no default (a test fails otherwise).
    with pytest.raises(TypeError):
        SignalProvenance("orphan")  # type: ignore[call-arg]


def test_naive_source_satisfies_protocol():
    assert isinstance(NaiveSignalSource(), SignalSource)


def test_procurement_signal_is_immutable():
    signal = NaiveSignalSource().assess(_market([2.00, 2.20]))
    with pytest.raises(Exception):
        signal.action = Action.WAIT  # type: ignore[misc]
