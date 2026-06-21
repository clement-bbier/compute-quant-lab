"""Révision tardive (§6c) — le piège des données macro « real-time » (vintages).

Un même ``value_ts`` peut être republié plus tard avec une valeur révisée. À
l'instant ``t``, seule la révision déjà publiée (``knowledge_ts <= t``) est visible :
une révision future ne doit jamais réécrire une feature historique.
"""

from __future__ import annotations

import pandas as pd

from core.features.builders import as_of_snapshot
from core.features.protocols import KNOWLEDGE_TS, VALUE, VALUE_TS


def _vintages(records):
    return pd.DataFrame([{VALUE_TS: v, KNOWLEDGE_TS: k, VALUE: x} for v, k, x in records])


def test_late_revision_not_seen_before_it_is_published(day_ts):
    # value_ts = D0 : v1=100 publié à D2, puis révisé v2=150 publié à D30.
    vintages = _vintages([(day_ts(0), day_ts(2), 100.0), (day_ts(0), day_ts(30), 150.0)])
    assert as_of_snapshot(vintages, day_ts(5)).loc[day_ts(0)] == 100.0  # v1 (avant révision)
    assert as_of_snapshot(vintages, day_ts(40)).loc[day_ts(0)] == 150.0  # v2 (après révision)


def test_historical_feature_is_stable_under_later_revision(day_ts):
    # La feature calculée à un ancien t (D5) ne change pas parce qu'une révision
    # est survenue depuis : as_of à D5 ignore tout knowledge_ts > D5.
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
            (day_ts(0), day_ts(30), 150.0),  # révision future de D0
            (day_ts(1), day_ts(3), 210.0),
        ]
    )
    snap = as_of_snapshot(vintages, day_ts(5))
    assert snap.loc[day_ts(0)] == 100.0  # dernier vintage connu de D0 = v1
    assert snap.loc[day_ts(1)] == 210.0
    assert len(snap) == 2
