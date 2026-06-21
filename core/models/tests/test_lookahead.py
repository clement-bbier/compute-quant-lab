"""Anti-look-ahead bout-en-bout via la brique P07 (features exogènes vintage).

La pipeline P09 réutilise le garde-fou point-in-time de ``core.features`` (P07) pour les
variables exogènes : à ``t``, seules les observations dont le ``knowledge_ts <= t`` entrent
dans la matrice. On le prouve par invariance à la falsification d'un millésime non encore publié.
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
    """Source exogène minimale (implémente ``ExogenousSource``) servant un frame vintage."""

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
    """Falsifier un millésime publié *après* ``t`` ne change pas la feature à ``t``."""
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

    # À t, la dernière valeur gaz connue date de value_ts <= t - lag. Saccager le futur
    # (millésimes dont knowledge_ts > t) ne doit pas bouger la ligne.
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
