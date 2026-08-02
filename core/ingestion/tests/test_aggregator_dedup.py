"""Direct > aggregator preference in the spot index (no venue double-counting).

Prime Intellect relays other providers' inventory under ``primeintellect:<venue>``, so
that quote and the direct ``<venue>`` feed describe the same underlying capacity. Both
entering the estimator overweights the venue and skews the outlier statistics
(``docs/decisions/004-provider-registry-architecture.md``).
"""

from __future__ import annotations

import datetime as dt

import pytest

from core.ingestion.compute_index import (
    DEFAULT_INDEX_CONFIG,
    IndexConfig,
    build_spot_index,
    prefer_direct_venues,
    split_source,
)
from core.ingestion.estimators import MadOutlierFilter, TrimmedMean
from core.ingestion.protocols import Snapshot, VenueRate

_TS = dt.datetime(2026, 6, 21, 12, 0, tzinfo=dt.timezone.utc)


def _snap(source: str, price: float) -> Snapshot:
    return Snapshot(
        snapshotted_at=_TS,
        source=source,
        gpu_model="H100",
        price_usd_per_hour=price,
        lease_type="on_demand",
        availability=1,
        simulated=False,
    )


def _rate(source: str, price: float) -> VenueRate:
    return VenueRate(source=source, rate=price, availability=1, snapshotted_at=_TS)


# --------------------------------------------------------------------------- #
# split_source
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("datacrunch", (None, "datacrunch")),
        ("primeintellect", (None, "primeintellect")),
        ("primeintellect:datacrunch", ("primeintellect", "datacrunch")),
        ("primeintellect:runpod", ("primeintellect", "runpod")),
    ],
)
def test_split_source(source: str, expected: tuple[str | None, str]) -> None:
    assert split_source(source) == expected


# --------------------------------------------------------------------------- #
# prefer_direct_venues
# --------------------------------------------------------------------------- #


def test_drops_aggregator_quote_when_venue_is_direct() -> None:
    rates = [_rate("datacrunch", 2.0), _rate("primeintellect:datacrunch", 2.4)]
    assert [r.source for r in prefer_direct_venues(rates)] == ["datacrunch"]


def test_keeps_aggregator_quote_when_venue_has_no_direct_feed() -> None:
    """An aggregator quote is the only observation of that venue: it must survive."""
    rates = [_rate("datacrunch", 2.0), _rate("primeintellect:lambda", 2.4)]
    assert [r.source for r in prefer_direct_venues(rates)] == [
        "datacrunch",
        "primeintellect:lambda",
    ]


def test_bare_aggregator_source_is_treated_as_a_direct_venue() -> None:
    """Unqualified ``primeintellect`` is its own inventory, not a relay."""
    rates = [_rate("primeintellect", 2.0), _rate("runpod", 2.2)]
    assert len(prefer_direct_venues(rates)) == 2


def test_preserves_input_order_and_is_idempotent() -> None:
    rates = [
        _rate("primeintellect:datacrunch", 2.4),
        _rate("runpod", 2.2),
        _rate("datacrunch", 2.0),
    ]
    once = prefer_direct_venues(rates)
    assert [r.source for r in once] == ["runpod", "datacrunch"]
    assert [r.source for r in prefer_direct_venues(once)] == ["runpod", "datacrunch"]


def test_no_op_when_nothing_overlaps() -> None:
    rates = [_rate("datacrunch", 2.0), _rate("runpod", 2.2), _rate("vastai", 2.1)]
    assert prefer_direct_venues(rates) == rates


# --------------------------------------------------------------------------- #
# build_spot_index integration
# --------------------------------------------------------------------------- #


def _mean_config(*, prefer_direct: bool) -> IndexConfig:
    """Plain mean, no trimming or rejection, so the price reflects venue weights exactly."""
    return IndexConfig(
        estimator=TrimmedMean(0.0),
        outlier_filter=MadOutlierFilter(1e9),
        prefer_direct=prefer_direct,
    )


def test_index_ignores_the_relayed_duplicate() -> None:
    """The direct quote alone represents datacrunch, so the fix is mean(2.0, 3.0)."""
    snapshots = [
        _snap("datacrunch", 2.0),
        _snap("primeintellect:datacrunch", 10.0),  # relayed duplicate, discarded
        _snap("runpod", 3.0),
    ]

    point = build_spot_index(snapshots, _TS, "H100", config=_mean_config(prefer_direct=True))

    assert point.n_sources == 2
    assert point.price_usd_per_hour == pytest.approx(2.5)


def test_disabling_the_policy_restores_the_double_count() -> None:
    """Pins the defect the policy fixes: the duplicate pulls the fix upward."""
    snapshots = [
        _snap("datacrunch", 2.0),
        _snap("primeintellect:datacrunch", 10.0),
        _snap("runpod", 3.0),
    ]

    point = build_spot_index(snapshots, _TS, "H100", config=_mean_config(prefer_direct=False))

    assert point.n_sources == 3
    assert point.price_usd_per_hour == pytest.approx(5.0)


def test_relayed_venue_survives_without_a_direct_feed() -> None:
    """Nothing is dropped when the aggregator is the only route to that venue."""
    snapshots = [_snap("primeintellect:lambda", 2.0), _snap("runpod", 3.0)]

    point = build_spot_index(snapshots, _TS, "H100", config=_mean_config(prefer_direct=True))

    assert point.n_sources == 2
    assert point.price_usd_per_hour == pytest.approx(2.5)


def test_policy_is_enabled_by_default() -> None:
    assert DEFAULT_INDEX_CONFIG.prefer_direct is True


def test_method_label_is_unchanged_by_the_policy() -> None:
    """``method`` names the estimator/filter pair only -- a stable consumer contract.

    The dedup happens upstream of estimation and stays observable through
    ``n_sources``, so it must not perturb this label (projects 03-06 assert on it).
    """
    assert DEFAULT_INDEX_CONFIG.method == "trimmed_mean20+mad2.5"
    assert _mean_config(prefer_direct=True).method == _mean_config(prefer_direct=False).method
