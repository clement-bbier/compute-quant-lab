"""The lab's point-in-time feature engineering (Strategy layer, P07).

Reusable building blocks to construct **exogenous** features (gas, weather, ...)
without look-ahead: each feature at ``t`` uses only data whose *knowledge-timestamp*
is ``<= t``. Reused downstream by P09 (ML).
"""

from core.features.builders import (
    DEFAULT_PUBLICATION_LAGS,
    FeatureSpec,
    LookAheadError,
    PointInTimeFeatureBuilder,
    as_of_snapshot,
    assert_point_in_time,
    diff_feature,
    from_lagged_series,
    lag_feature,
    rolling_mean_feature,
)
from core.features.protocols import (
    KNOWLEDGE_TS,
    VALUE,
    VALUE_TS,
    VINTAGE_COLUMNS,
    ExogenousSource,
    FeatureBuilder,
    FloatArray,
)

__all__ = [
    # Point-in-time machinery.
    "as_of_snapshot",
    "from_lagged_series",
    "assert_point_in_time",
    "LookAheadError",
    # Pure transforms.
    "lag_feature",
    "rolling_mean_feature",
    "diff_feature",
    # Builder.
    "FeatureSpec",
    "PointInTimeFeatureBuilder",
    "DEFAULT_PUBLICATION_LAGS",
    # Contracts.
    "ExogenousSource",
    "FeatureBuilder",
    "FloatArray",
    # Vintage schema.
    "VALUE_TS",
    "KNOWLEDGE_TS",
    "VALUE",
    "VINTAGE_COLUMNS",
]
