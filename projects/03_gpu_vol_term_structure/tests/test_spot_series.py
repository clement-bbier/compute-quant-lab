"""Tests of spot series construction (glue consuming ``core.ingestion``).

``build_spot_series`` replays ``build_spot_index`` over a fix grid. Two guarantees:
- **point-in-time**: a reading posterior to a fix does not modify that fix (anti look-ahead);
- **robustness**: an instant with no fresh data is ignored (no fabricated point).
"""

from __future__ import annotations

import datetime as dt

import numpy as np

from core.ingestion.protocols import Snapshot

from spot_series import build_spot_series

_GPU = "H100"
_DAY1 = dt.datetime(2026, 6, 19, 0, 30, tzinfo=dt.timezone.utc)
_DAY2 = dt.datetime(2026, 6, 20, 0, 30, tzinfo=dt.timezone.utc)
_DAY0 = dt.datetime(2026, 6, 1, 0, 30, tzinfo=dt.timezone.utc)  # before any data


def _snaps_two_days() -> list[Snapshot]:
    return [
        Snapshot(
            _DAY1 - dt.timedelta(hours=1), "vastai", _GPU, 2.00, availability=100, simulated=False
        ),
        Snapshot(
            _DAY1 - dt.timedelta(hours=2), "runpod", _GPU, 2.10, availability=50, simulated=False
        ),
        Snapshot(
            _DAY2 - dt.timedelta(hours=1), "vastai", _GPU, 2.40, availability=100, simulated=False
        ),
        Snapshot(
            _DAY2 - dt.timedelta(hours=2), "runpod", _GPU, 2.50, availability=50, simulated=False
        ),
    ]


def test_build_spot_series_returns_one_price_per_resolvable_fix() -> None:
    times, prices = build_spot_series(_snaps_two_days(), [_DAY1, _DAY2], _GPU)
    assert len(times) == 2
    assert prices.shape == (2,)
    assert prices[1] > prices[0]  # the level rises from DAY1 to DAY2


def test_grid_point_without_fresh_data_is_skipped() -> None:
    times, prices = build_spot_series(_snaps_two_days(), [_DAY0, _DAY1, _DAY2], _GPU)
    # _DAY0 has no fresh data (readings well after it) -> ignored.
    assert len(times) == 2
    assert _DAY0 not in times


def test_future_snapshot_does_not_change_past_fix() -> None:
    """Anti look-ahead: adding a future reading leaves earlier fixes unchanged."""
    base = _snaps_two_days()
    _, prices_base = build_spot_series(base, [_DAY1, _DAY2], _GPU)

    future = base + [
        Snapshot(
            _DAY2 + dt.timedelta(days=1), "vastai", _GPU, 9.99, availability=100, simulated=False
        )
    ]
    _, prices_future = build_spot_series(future, [_DAY1, _DAY2], _GPU)

    assert np.array_equal(prices_base, prices_future)
