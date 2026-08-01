"""Building the feature matrix and the directional target (point-in-time).

`build_labels` encodes the **future direction** of the spread (binary target).
`FeaturePipeline` assembles two feature sources, all causal (``<= t``):

* features derived from the spread itself (lags, rolling means, momentum) — causal by
  construction (positive ``shift``, backward ``rolling``);
* point-in-time exogenous features from **P07** (`core.features`), if a builder is injected:
  at ``t``, only the observations whose ``knowledge_ts <= t`` enter (publication lags +
  revisions handled upstream).

The target is NEVER a feature: `build_labels` looks at ``t+horizon`` (the future), which
makes it a training label, never an input of the model at inference time.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from core.features.protocols import FeatureBuilder


def build_labels(spread: pd.Series, *, horizon: int) -> pd.Series:
    """Directional target: ``1`` if the spread rises over ``horizon`` steps, ``0`` otherwise.

    The last ``horizon`` rows have no observable future -> ``NaN`` (excluded from training).
    This is the only honest way to bound the learning set.
    """
    if horizon < 1:
        raise ValueError(f"horizon ({horizon}) must be >= 1.")
    forward_move = spread.shift(-horizon) - spread
    direction = (forward_move > 0.0).astype(float)
    direction[forward_move.isna()] = np.nan
    direction.name = "direction"
    return direction


@dataclass(frozen=True)
class SpreadFeatureSpec:
    """Causal transforms to derive from the spread (all ``<= t`` by construction)."""

    lags: tuple[int, ...] = ()
    rolling_means: tuple[int, ...] = ()
    momentums: tuple[int, ...] = field(default=())


class FeaturePipeline:
    """Assemble a point-in-time feature matrix (spread + P07 exogenous features).

    Parameters
    ----------
    spread_spec
        Which features to derive from the spread.
    exog_builder
        Optional P07 point-in-time builder (`FeatureBuilder`) for the exogenous variables.
    """

    def __init__(
        self,
        *,
        spread_spec: SpreadFeatureSpec,
        exog_builder: FeatureBuilder | None = None,
    ) -> None:
        self._spread_spec = spread_spec
        self._exog_builder = exog_builder

    def _spread_features(self, spread: pd.Series) -> pd.DataFrame:
        columns: dict[str, pd.Series] = {}
        for k in self._spread_spec.lags:
            columns[f"spread_lag{k}"] = spread.shift(k)
        for w in self._spread_spec.rolling_means:
            columns[f"spread_roll{w}"] = spread.rolling(w).mean()
        for k in self._spread_spec.momentums:
            columns[f"spread_mom{k}"] = spread - spread.shift(k)
        return pd.DataFrame(columns, index=spread.index)

    def build_matrix(self, spread: pd.Series) -> pd.DataFrame:
        """Feature matrix (one row per decision instant = index of the spread)."""
        if not isinstance(spread.index, pd.DatetimeIndex):
            raise ValueError("spread must be indexed by a DatetimeIndex (point-in-time).")
        matrix = self._spread_features(spread)
        if self._exog_builder is not None:
            exog = self._exog_builder.build_panel(spread.index)
            matrix = pd.concat([matrix, exog], axis=1)
        return matrix


__all__ = ["build_labels", "SpreadFeatureSpec", "FeaturePipeline"]
