"""Pipeline de features & labels directionnels (point-in-time strict).

Prouve que (a) le label encode bien le signe du *forward return* au bon horizon, et
(b) la matrice de features à ``t`` ne dépend QUE de données ``<= t`` (invariance par
troncature du futur). C'est la première des trois défenses anti-look-ahead.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from core.models.pipeline import FeaturePipeline, SpreadFeatureSpec, build_labels


def test_labels_encode_forward_direction(spread_series) -> None:
    horizon = 3
    y = build_labels(spread_series, horizon=horizon)
    fwd = spread_series.shift(-horizon) - spread_series
    expected = (fwd > 0).astype(float)
    mask = fwd.notna()
    assert np.array_equal(y[mask].to_numpy(), expected[mask].to_numpy())


def test_labels_are_nan_on_the_unobservable_tail(spread_series) -> None:
    horizon = 4
    y = build_labels(spread_series, horizon=horizon)
    assert y.iloc[-horizon:].isna().all()
    assert y.iloc[:-horizon].notna().all()


def test_matrix_is_aligned_on_decision_index(spread_series) -> None:
    pipeline = FeaturePipeline(
        spread_spec=SpreadFeatureSpec(lags=(1, 2), rolling_means=(5,), momentums=(3,))
    )
    matrix = pipeline.build_matrix(spread_series)
    assert matrix.index.equals(spread_series.index)
    assert "spread_lag1" in matrix.columns
    assert "spread_roll5" in matrix.columns
    assert "spread_mom3" in matrix.columns


def test_spread_features_are_point_in_time(spread_series) -> None:
    """Invariance par troncature : altérer le futur ne change pas la ligne à ``t``."""
    pipeline = FeaturePipeline(
        spread_spec=SpreadFeatureSpec(lags=(1, 2), rolling_means=(5,), momentums=(3,))
    )
    full = pipeline.build_matrix(spread_series)

    t = 100
    tampered = spread_series.copy()
    tampered.iloc[t + 1 :] += 999.0  # on saccage tout le futur strict de t
    tampered_matrix = pipeline.build_matrix(tampered)

    pd.testing.assert_series_equal(full.iloc[t], tampered_matrix.iloc[t])


def test_warmup_rows_are_nan(spread_series) -> None:
    pipeline = FeaturePipeline(spread_spec=SpreadFeatureSpec(rolling_means=(10,)))
    matrix = pipeline.build_matrix(spread_series)
    assert matrix["spread_roll10"].iloc[:9].isna().all()
    assert matrix["spread_roll10"].iloc[9:].notna().all()
