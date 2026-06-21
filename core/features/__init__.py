"""Feature engineering point-in-time du labo (couche Stratégie, P07).

Briques réutilisables pour construire des features **exogènes** (gaz, météo…)
sans look-ahead : chaque feature à ``t`` n'utilise que des données dont le
*knowledge-timestamp* est ``<= t``. Réutilisé en aval par P09 (ML).
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
    # Mécanique point-in-time.
    "as_of_snapshot",
    "from_lagged_series",
    "assert_point_in_time",
    "LookAheadError",
    # Transforms purs.
    "lag_feature",
    "rolling_mean_feature",
    "diff_feature",
    # Builder.
    "FeatureSpec",
    "PointInTimeFeatureBuilder",
    "DEFAULT_PUBLICATION_LAGS",
    # Contrats.
    "ExogenousSource",
    "FeatureBuilder",
    "FloatArray",
    # Schéma vintage.
    "VALUE_TS",
    "KNOWLEDGE_TS",
    "VALUE",
    "VINTAGE_COLUMNS",
]
