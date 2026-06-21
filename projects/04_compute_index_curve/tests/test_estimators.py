"""Tests unitaires des stratégies d'agrégation (filtres + estimateurs).

Chaque stratégie est testée en isolation : c'est l'intérêt du pattern Strategy —
les briques d'agrégation sont vérifiables indépendamment du pipeline d'indice.
"""

from __future__ import annotations

import datetime as dt

import pytest

from core.ingestion.estimators import (
    AvailabilityWeightedMean,
    MadOutlierFilter,
    Median,
    NoOutlierFilter,
    TrimmedMean,
)
from core.ingestion.protocols import VenueRate

_TS = dt.datetime(2026, 6, 21, tzinfo=dt.timezone.utc)


def _vr(rate: float, availability: int = 0, source: str = "s") -> VenueRate:
    return VenueRate(source=source, rate=rate, availability=availability, snapshotted_at=_TS)


def test_mad_filter_rejects_far_outlier() -> None:
    rates = [
        _vr(2.00, source="a"),
        _vr(2.20, source="b"),
        _vr(2.10, source="c"),
        _vr(2.30, source="d"),
        _vr(0.05, source="e"),  # aberrant
    ]
    kept = MadOutlierFilter(2.5).filter(rates)
    assert {r.source for r in kept} == {"a", "b", "c", "d"}


def test_mad_filter_keeps_all_when_no_spread() -> None:
    rates = [_vr(2.0), _vr(2.0), _vr(2.0)]
    assert len(MadOutlierFilter(2.5).filter(rates)) == 3


def test_mad_filter_name() -> None:
    assert MadOutlierFilter(2.5).name == "mad2.5"


def test_no_outlier_filter_keeps_everything() -> None:
    rates = [_vr(2.0), _vr(0.01), _vr(99.0)]
    assert len(NoOutlierFilter().filter(rates)) == 3
    assert NoOutlierFilter().name == "nofilter"


def test_trimmed_mean_trims_extremes() -> None:
    # sorted [1,1,1,1,100], trim 20% -> k=1 -> coeur [1,1,1] -> moyenne 1.0
    rates = [_vr(1), _vr(1), _vr(1), _vr(1), _vr(100)]
    assert TrimmedMean(0.20).estimate(rates) == pytest.approx(1.0)
    assert TrimmedMean(0.20).name == "trimmed_mean20"


def test_trimmed_mean_no_trim_when_few_points() -> None:
    # n=4, trim 0.20 -> k=0 -> moyenne simple
    rates = [_vr(2.00), _vr(2.10), _vr(2.20), _vr(2.30)]
    assert TrimmedMean(0.20).estimate(rates) == pytest.approx(2.15)


def test_median_estimator() -> None:
    rates = [_vr(1), _vr(2), _vr(3), _vr(4)]
    assert Median().estimate(rates) == pytest.approx(2.5)
    assert Median().name == "median"


def test_availability_weighted_mean() -> None:
    # (2*100 + 4*300) / 400 = 3.5
    rates = [_vr(2.0, availability=100, source="a"), _vr(4.0, availability=300, source="b")]
    assert AvailabilityWeightedMean().estimate(rates) == pytest.approx(3.5)
    assert AvailabilityWeightedMean().name == "avail_weighted"


def test_availability_weighted_falls_back_to_equal_weight() -> None:
    # availabilities nulles -> moyenne équipondérée
    rates = [_vr(2.0, availability=0), _vr(4.0, availability=0)]
    assert AvailabilityWeightedMean().estimate(rates) == pytest.approx(3.0)
