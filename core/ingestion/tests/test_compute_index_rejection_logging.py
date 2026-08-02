"""V7.2 observability: compute_index rejections are counted and logged as an audit summary.

``build_spot_index`` silently dropped observations at four stages (hyperscaler exclusion,
staleness, direct-over-aggregator dedup, MAD outlier rejection) with no visibility into how
many were rejected at each stage -- yet this is exactly the audit trail behind a published
price. One INFO summary line per successful fix, one WARNING when no fresh venue survives.
"""

from __future__ import annotations

import datetime as dt
import logging

import pytest

from core.ingestion.compute_index import (
    IndexConfig,
    InsufficientDataError,
    build_spot_index,
)
from core.ingestion.estimators import MadOutlierFilter, TrimmedMean
from core.ingestion.protocols import Snapshot

_TS = dt.datetime(2026, 6, 21, 12, 0, tzinfo=dt.timezone.utc)


def _snap(source: str, price: float, *, age: dt.timedelta = dt.timedelta(0)) -> Snapshot:
    return Snapshot(
        snapshotted_at=_TS - age,
        source=source,
        gpu_model="H100",
        price_usd_per_hour=price,
        lease_type="on_demand",
        availability=1,
    )


def _mean_config(**overrides: object) -> IndexConfig:
    defaults: dict[str, object] = {
        "estimator": TrimmedMean(0.0),
        "outlier_filter": MadOutlierFilter(1e9),
    }
    defaults.update(overrides)
    return IndexConfig(**defaults)  # type: ignore[arg-type]


def test_successful_fix_logs_summary_with_zero_rejections(
    caplog: pytest.LogCaptureFixture,
) -> None:
    snapshots = [_snap("datacrunch", 2.0), _snap("runpod", 3.0)]

    with caplog.at_level(logging.INFO):
        build_spot_index(snapshots, _TS, "H100", config=_mean_config())

    assert "2 source(s) kept" in caplog.text
    assert "hyperscaler=0" in caplog.text
    assert "stale=0" in caplog.text
    assert "direct_over_aggregator=0" in caplog.text
    assert "mad_outlier=0" in caplog.text


def test_hyperscaler_exclusion_is_counted(caplog: pytest.LogCaptureFixture) -> None:
    snapshots = [_snap("datacrunch", 2.0), _snap("runpod", 3.0), _snap("aws", 100.0)]

    with caplog.at_level(logging.INFO):
        build_spot_index(snapshots, _TS, "H100", config=_mean_config())

    assert "hyperscaler=1" in caplog.text


def test_staleness_rejection_is_counted(caplog: pytest.LogCaptureFixture) -> None:
    snapshots = [
        _snap("datacrunch", 2.0),
        _snap("runpod", 3.0),
        _snap("cudo", 5.0, age=dt.timedelta(hours=48)),  # older than the 24h default staleness
    ]

    with caplog.at_level(logging.INFO):
        build_spot_index(snapshots, _TS, "H100", config=_mean_config())

    assert "stale=1" in caplog.text


def test_direct_over_aggregator_rejection_is_counted(caplog: pytest.LogCaptureFixture) -> None:
    snapshots = [
        _snap("datacrunch", 2.0),
        _snap("primeintellect:datacrunch", 10.0),
        _snap("runpod", 3.0),
    ]

    with caplog.at_level(logging.INFO):
        build_spot_index(snapshots, _TS, "H100", config=_mean_config(prefer_direct=True))

    assert "direct_over_aggregator=1" in caplog.text


def test_mad_outlier_rejection_is_counted(caplog: pytest.LogCaptureFixture) -> None:
    # A tight MAD filter (k=1.0) around a near-zero spread cluster (2.0/2.05/2.1) rejects
    # both the far outlier (500.0) and the cluster tail farthest from the median (2.0) --
    # this pins the filter's actual behaviour, not an assumption about it.
    snapshots = [
        _snap("datacrunch", 2.0),
        _snap("runpod", 2.1),
        _snap("cudo", 2.05),
        _snap("hyperstack", 500.0),
    ]

    with caplog.at_level(logging.INFO):
        build_spot_index(
            snapshots, _TS, "H100", config=_mean_config(outlier_filter=MadOutlierFilter(1.0))
        )

    assert "mad_outlier=2" in caplog.text


def test_no_fresh_venue_logs_warning_with_counts(caplog: pytest.LogCaptureFixture) -> None:
    snapshots = [_snap("aws", 2.0), _snap("datacrunch", 3.0, age=dt.timedelta(hours=48))]

    with caplog.at_level(logging.WARNING), pytest.raises(InsufficientDataError):
        build_spot_index(snapshots, _TS, "H100", config=_mean_config())

    assert "no fresh venue" in caplog.text.lower()
    assert "hyperscaler-excluded" in caplog.text
    assert "stale-rejected" in caplog.text
