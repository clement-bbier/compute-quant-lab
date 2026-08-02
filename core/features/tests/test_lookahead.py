"""STRICT anti look-ahead (section 6a) — the "expected red" of P07.

A feature at ``t`` must NEVER consume a value whose knowledge-timestamp exceeds ``t``.
Both sides are tested: (1) the point-in-time snapshot excludes the not-yet-published;
(2) the `assert_point_in_time` guardrail *raises* when faced with cheating, exactly like
`core.backtest.tests.test_guards` on the backtest side.
"""

from __future__ import annotations

import pandas as pd
import pytest

from core.features.builders import (
    LookAheadError,
    as_of_snapshot,
    assert_point_in_time,
    from_lagged_series,
)


def _series(day_ts, values: list[float]) -> pd.Series:
    idx = pd.DatetimeIndex([day_ts(i) for i in range(len(values))])
    return pd.Series(values, index=idx)


def test_asof_excludes_values_not_yet_published(day_ts):
    # value_ts D0, D1; publication lag = 2 days (known at D2, D3).
    vintages = from_lagged_series(_series(day_ts, [100.0, 200.0]), pd.Timedelta("2D"))

    # At D1: nothing is published yet -> empty snapshot (no look-ahead possible).
    assert as_of_snapshot(vintages, day_ts(1)).empty

    # At D2: only D0 is known; D1 (published at D3) stays invisible.
    snap = as_of_snapshot(vintages, day_ts(2))
    assert list(snap.index) == [day_ts(0)]
    assert snap.loc[day_ts(0)] == 100.0
    assert day_ts(1) not in snap.index


def test_guard_raises_when_used_knowledge_exceeds_asof(day_ts):
    # Real calendar: values published at D2 and D3.
    used_knowledge = pd.Series([day_ts(2), day_ts(3)])
    with pytest.raises(LookAheadError):
        assert_point_in_time(day_ts(1), used_knowledge)  # D2, D3 > D1 -> cheating


def test_guard_logs_error_when_raising(day_ts, caplog):
    """V7.2: a look-ahead violation must be visible in the logs, not just via the raise."""
    used_knowledge = pd.Series([day_ts(2), day_ts(3)])
    with caplog.at_level("ERROR"), pytest.raises(LookAheadError):
        assert_point_in_time(day_ts(1), used_knowledge)
    assert "used_knowledge_ts" in caplog.text


def test_guard_passes_when_everything_is_already_known(day_ts):
    used_knowledge = pd.Series([day_ts(2), day_ts(3)])
    assert_point_in_time(day_ts(3), used_knowledge)  # everything <= D3: does not raise


def test_publication_lag_is_what_prevents_the_leak(day_ts):
    # Demonstration: ignoring the lag (lag=0) leaks an unpublished value.
    s = _series(day_ts, [100.0, 200.0])
    correct = as_of_snapshot(from_lagged_series(s, pd.Timedelta("2D")), day_ts(1))
    naive = as_of_snapshot(from_lagged_series(s, pd.Timedelta("0D")), day_ts(1))

    assert correct.empty  # at D1, nothing is known with the real lag
    assert day_ts(1) in naive.index  # the naive one already "knows" the D1 value
    assert not correct.equals(naive)  # the lag changes the result -> it matters
