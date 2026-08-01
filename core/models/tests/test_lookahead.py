"""End-to-end anti-look-ahead via the P07 block (vintage exogenous features).

The P09 pipeline reuses the point-in-time guardrail of ``core.features`` (P07) for the
exogenous variables: at ``t``, only the observations whose ``knowledge_ts <= t`` enter the
matrix. This is proven by invariance to tampering with a not-yet-published vintage.
"""

from __future__ import annotations

import pandas as pd

from core.features import (
    FeatureSpec,
    PointInTimeFeatureBuilder,
    from_lagged_series,
)
from core.features.protocols import ExogenousSource
from core.models.pipeline import FeaturePipeline, SpreadFeatureSpec


class _InMemorySource:
    """Minimal exogenous source (implements ``ExogenousSource``) serving a vintage frame."""

    def __init__(self, vintages: dict[str, pd.DataFrame]) -> None:
        self._vintages = vintages

    def names(self) -> list[str]:
        return list(self._vintages)

    def vintages(self, name: str) -> pd.DataFrame:
        return self._vintages[name]


def _utc_index(n: int) -> pd.DatetimeIndex:
    return pd.date_range("2025-01-01", periods=n, freq="h", tz="UTC")


def _source_conforms_to_p07_contract() -> None:
    src = _InMemorySource(
        {"gas": from_lagged_series(pd.Series([1.0], _utc_index(1)), pd.Timedelta("1D"))}
    )
    assert isinstance(src, ExogenousSource)


def test_exogenous_features_respect_publication_lag() -> None:
    """Tampering with a vintage published *after* ``t`` does not change the feature at ``t``."""
    n = 120
    idx = _utc_index(n)
    gas = pd.Series(range(n), index=idx, dtype=float)
    lag = pd.Timedelta("3h")
    builder = PointInTimeFeatureBuilder(
        source=_InMemorySource({"gas": from_lagged_series(gas, lag)}),
        specs={"gas": FeatureSpec(lags=(0,))},
    )
    spread = pd.Series(range(n), index=idx, dtype=float)
    pipeline = FeaturePipeline(spread_spec=SpreadFeatureSpec(lags=(1,)), exog_builder=builder)
    full = pipeline.build_matrix(spread)

    # At t, the last known gas value dates from value_ts <= t - lag. Wrecking the future
    # (vintages whose knowledge_ts > t) must not move the row.
    t = 50
    tampered_gas = gas.copy()
    tampered_gas.iloc[t:] += 1000.0
    tampered_builder = PointInTimeFeatureBuilder(
        source=_InMemorySource({"gas": from_lagged_series(tampered_gas, lag)}),
        specs={"gas": FeatureSpec(lags=(0,))},
    )
    tampered_pipeline = FeaturePipeline(
        spread_spec=SpreadFeatureSpec(lags=(1,)), exog_builder=tampered_builder
    )
    tampered = tampered_pipeline.build_matrix(spread)

    assert full["gas_lag0"].iloc[t] == tampered["gas_lag0"].iloc[t]


def test_exogenous_columns_are_merged_into_the_matrix() -> None:
    n = 60
    idx = _utc_index(n)
    gas = pd.Series(range(n), index=idx, dtype=float)
    builder = PointInTimeFeatureBuilder(
        source=_InMemorySource({"gas": from_lagged_series(gas, pd.Timedelta("1h"))}),
        specs={"gas": FeatureSpec(lags=(0,), rolling_means=(3,))},
    )
    spread = pd.Series(range(n), index=idx, dtype=float)
    pipeline = FeaturePipeline(spread_spec=SpreadFeatureSpec(lags=(1,)), exog_builder=builder)
    matrix = pipeline.build_matrix(spread)
    assert {"spread_lag1", "gas_lag0", "gas_roll3"} <= set(matrix.columns)
    assert matrix.index.equals(idx)
