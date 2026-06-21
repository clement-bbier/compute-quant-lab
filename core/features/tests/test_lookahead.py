"""Anti look-ahead STRICT (§6a) — le « rouge attendu » de P07.

Une feature à ``t`` ne doit JAMAIS consommer une valeur dont le knowledge-timestamp
dépasse ``t``. On teste les deux faces : (1) le snapshot point-in-time exclut le
non-encore-publié ; (2) le garde-fou `assert_point_in_time` *lève* face à une triche,
exactement comme `core.backtest.tests.test_guards` côté backtest.
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
    # value_ts D0, D1 ; lag de publication = 2 jours (connus à D2, D3).
    vintages = from_lagged_series(_series(day_ts, [100.0, 200.0]), pd.Timedelta("2D"))

    # À D1 : rien n'est encore publié → snapshot vide (aucun look-ahead possible).
    assert as_of_snapshot(vintages, day_ts(1)).empty

    # À D2 : seul D0 est connu ; D1 (publié à D3) reste invisible.
    snap = as_of_snapshot(vintages, day_ts(2))
    assert list(snap.index) == [day_ts(0)]
    assert snap.loc[day_ts(0)] == 100.0
    assert day_ts(1) not in snap.index


def test_guard_raises_when_used_knowledge_exceeds_asof(day_ts):
    # Calendrier réel : valeurs publiées à D2 et D3.
    used_knowledge = pd.Series([day_ts(2), day_ts(3)])
    with pytest.raises(LookAheadError):
        assert_point_in_time(day_ts(1), used_knowledge)  # D2, D3 > D1 → triche


def test_guard_passes_when_everything_is_already_known(day_ts):
    used_knowledge = pd.Series([day_ts(2), day_ts(3)])
    assert_point_in_time(day_ts(3), used_knowledge)  # tout <= D3 : ne lève pas


def test_publication_lag_is_what_prevents_the_leak(day_ts):
    # Démonstration : ignorer le lag (lag=0) fait fuir une valeur non publiée.
    s = _series(day_ts, [100.0, 200.0])
    correct = as_of_snapshot(from_lagged_series(s, pd.Timedelta("2D")), day_ts(1))
    naive = as_of_snapshot(from_lagged_series(s, pd.Timedelta("0D")), day_ts(1))

    assert correct.empty  # à D1, rien n'est connu avec le vrai lag
    assert day_ts(1) in naive.index  # le naïf « connaît » déjà la valeur de D1
    assert not correct.equals(naive)  # le lag change le résultat → il compte
