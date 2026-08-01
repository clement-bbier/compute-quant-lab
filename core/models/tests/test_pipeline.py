"""Feature pipeline & directional labels (strict point-in-time).

Proves that (a) the label does encode the sign of the *forward return* at the right horizon,
and (b) the feature matrix at ``t`` depends ONLY on data ``<= t`` (invariance under
truncation of the future). This is the first of the three anti-look-ahead defenses.
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
    """Invariance under truncation: altering the future does not change the row at ``t``."""
    pipeline = FeaturePipeline(
        spread_spec=SpreadFeatureSpec(lags=(1, 2), rolling_means=(5,), momentums=(3,))
    )
    full = pipeline.build_matrix(spread_series)

    t = 100
    tampered = spread_series.copy()
    tampered.iloc[t + 1 :] += 999.0  # wreck the entire strict future of t
    tampered_matrix = pipeline.build_matrix(tampered)

    pd.testing.assert_series_equal(full.iloc[t], tampered_matrix.iloc[t])


def test_warmup_rows_are_nan(spread_series) -> None:
    pipeline = FeaturePipeline(spread_spec=SpreadFeatureSpec(rolling_means=(10,)))
    matrix = pipeline.build_matrix(spread_series)
    assert matrix["spread_roll10"].iloc[:9].isna().all()
    assert matrix["spread_roll10"].iloc[9:].notna().all()
