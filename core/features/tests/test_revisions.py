"""Late revision (section 6c) — the trap of "real-time" macro data (vintages).

The same ``value_ts`` can be republished later with a revised value. At instant ``t``,
only the already-published revision (``knowledge_ts <= t``) is visible: a future revision
must never rewrite a historical feature.
"""

from __future__ import annotations

import pandas as pd

from core.features.builders import as_of_snapshot
from core.features.protocols import KNOWLEDGE_TS, VALUE, VALUE_TS


def _vintages(records):
    return pd.DataFrame([{VALUE_TS: v, KNOWLEDGE_TS: k, VALUE: x} for v, k, x in records])


def test_late_revision_not_seen_before_it_is_published(day_ts):
    # value_ts = D0: v1=100 published at D2, then revised v2=150 published at D30.
    vintages = _vintages([(day_ts(0), day_ts(2), 100.0), (day_ts(0), day_ts(30), 150.0)])
    assert as_of_snapshot(vintages, day_ts(5)).loc[day_ts(0)] == 100.0  # v1 (before revision)
    assert as_of_snapshot(vintages, day_ts(40)).loc[day_ts(0)] == 150.0  # v2 (after revision)


def test_historical_feature_is_stable_under_later_revision(day_ts):
    # The feature computed at an old t (D5) does not change because a revision has
    # happened since: as_of at D5 ignores every knowledge_ts > D5.
    pre_revision = _vintages([(day_ts(0), day_ts(2), 100.0)])
    post_revision = _vintages([(day_ts(0), day_ts(2), 100.0), (day_ts(0), day_ts(30), 150.0)])
    assert (
        as_of_snapshot(pre_revision, day_ts(5)).loc[day_ts(0)]
        == as_of_snapshot(post_revision, day_ts(5)).loc[day_ts(0)]
        == 100.0
    )


def test_only_latest_known_vintage_per_value_ts(day_ts):
    vintages = _vintages(
        [
            (day_ts(0), day_ts(2), 100.0),
            (day_ts(0), day_ts(30), 150.0),  # future revision of D0
            (day_ts(1), day_ts(3), 210.0),
        ]
    )
    snap = as_of_snapshot(vintages, day_ts(5))
    assert snap.loc[day_ts(0)] == 100.0  # latest known vintage of D0 = v1
    assert snap.loc[day_ts(1)] == 210.0
    assert len(snap) == 2
