"""Building **point-in-time** exogenous features (strict anti look-ahead).

Heart of the P07 discipline. Any feature at decision instant ``t`` uses only
observations whose ``knowledge_ts <= t`` (see `protocols`). The mechanism generalizes
the publication shift of `core.pricing.sources.DataFramePriceSource` (which shifts the
index towards what is *known at t*) by **also handling revisions**: per ``value_ts``,
only the latest vintage published in time is kept.

Deliberate parallel with `core.backtest.guards.LookAheadError`: over there a *runtime*
guardrail for backtest signals; here the same intransigence at feature-building time.
The two modules stay decoupled (no cross-import).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from core.features.protocols import KNOWLEDGE_TS, VALUE, VALUE_TS, ExogenousSource
from core.utils.timeindex import to_utc_index

# ---------------------------------------------------------------------------
# Default publication lags — set by the research director.
#
# Each exogenous variable is only known with a delay. A lag that is too short =
# look-ahead; too long = exploitable signal is thrown away. *Conservative* default (we
# prefer over-estimating the delay). To be recalibrated against the real calendar when
# wiring the real connector (see CONVERGENCE); if the source exposes vintages, feed the
# vintage frames directly (revisions are handled by `as_of_snapshot`).
# ---------------------------------------------------------------------------
DEFAULT_PUBLICATION_LAGS: dict[str, pd.Timedelta] = {
    # Settlement gas index published D+1 (the day-ahead one would be known the day before).
    "gas_price": pd.Timedelta("1D"),
    # Realized temperature available D+1, + 1 day of margin against weather revisions.
    "hdd": pd.Timedelta("2D"),
    "cdd": pd.Timedelta("2D"),  # same as HDD (same realized temperature source).
}


class LookAheadError(RuntimeError):
    """Raised when a feature at ``t`` would consume data known only after ``t``."""


def from_lagged_series(
    values: pd.Series,
    publication_lag: pd.Timedelta,
) -> pd.DataFrame:
    """Build a vintage frame from a plain series + a publication lag.

    PoC case without real vintages: ``knowledge_ts = value_ts + lag`` is assumed.
    Revisions are modelled by concatenating several rows sharing the same ``value_ts``
    (distinct knowledge_ts) directly into the vintage frame.

    Parameters
    ----------
    values
        Series indexed by ``value_ts`` (tz-aware DatetimeIndex) -> observed value.
    publication_lag
        Delay between the period described and its publication (``Timedelta``).

    Returns
    -------
    pd.DataFrame
        Columns ``(value_ts, knowledge_ts, value)``, UTC timestamps.
    """
    value_ts = to_utc_index(values.index)
    return pd.DataFrame(
        {
            VALUE_TS: value_ts,
            KNOWLEDGE_TS: value_ts + publication_lag,
            VALUE: values.to_numpy(dtype=float),
        }
    )


def as_of_snapshot(vintages: pd.DataFrame, asof: pd.Timestamp) -> pd.Series:
    """Point-in-time snapshot: values known at ``asof`` (lag + revisions handled).

    1. keeps only the rows ``knowledge_ts <= asof`` (publication filter);
    2. per ``value_ts``, keeps the most recent ``knowledge_ts`` (latest known vintage —
       handles revisions);
    3. returns a series indexed by increasing ``value_ts``.

    An empty series (nothing published yet) is returned with an empty UTC index.
    """
    known = vintages[vintages[KNOWLEDGE_TS] <= asof]
    if known.empty:
        empty_index = pd.DatetimeIndex([], tz="UTC", name=VALUE_TS)
        return pd.Series([], index=empty_index, dtype=float)

    latest_rows = known.loc[known.groupby(VALUE_TS)[KNOWLEDGE_TS].idxmax()]
    snapshot = pd.Series(
        latest_rows[VALUE].to_numpy(dtype=float),
        index=pd.DatetimeIndex(latest_rows[VALUE_TS], name=VALUE_TS),
        dtype=float,
    )
    return snapshot.sort_index()


def assert_point_in_time(asof: pd.Timestamp, used_knowledge_ts: pd.Series) -> None:
    """Guardrail: raise `LookAheadError` if a used ``knowledge_ts`` exceeds ``asof``.

    Feature-side counterpart of the backtest guardrail: makes look-ahead **impossible to
    ignore** rather than silently correcting it.
    """
    offenders = used_knowledge_ts[used_knowledge_ts > asof]
    if not offenders.empty:
        raise LookAheadError(
            f"used_knowledge_ts ({len(offenders)} observation(s)) must be known at {asof}: "
            f"max knowledge_ts = {offenders.max()}"
        )


def lag_feature(snapshot: pd.Series, k: int) -> float:
    """Value lagged by ``k`` steps in the known snapshot (lag 0 = most recent)."""
    if k < 0:
        raise ValueError(f"k ({k}) must be a non-negative lag.")
    if k >= snapshot.shape[0]:
        return math.nan
    return float(snapshot.iloc[-1 - k])


def rolling_mean_feature(snapshot: pd.Series, window: int) -> float:
    """Mean of the last ``window`` known values (NaN if the history is too short)."""
    if window <= 0:
        raise ValueError(f"window ({window}) must be strictly positive.")
    if snapshot.shape[0] < window:
        return math.nan
    return float(snapshot.iloc[-window:].mean())


def diff_feature(snapshot: pd.Series, k: int) -> float:
    """Difference between the most recent value and the one lagged by ``k``."""
    latest = lag_feature(snapshot, 0)
    lagged = lag_feature(snapshot, k)
    if math.isnan(latest) or math.isnan(lagged):
        return math.nan
    return latest - lagged


@dataclass(frozen=True)
class FeatureSpec:
    """Which features to derive from a variable (all <= t by construction)."""

    lags: tuple[int, ...] = ()
    rolling_means: tuple[int, ...] = ()
    diffs: tuple[int, ...] = ()


class PointInTimeFeatureBuilder:
    """Injectable point-in-time builder (implements `FeatureBuilder`).

    Parameters
    ----------
    source
        Exogenous source (`ExogenousSource` protocol) serving the vintage frames.
    specs
        For each variable, the `FeatureSpec` of the transforms to derive.
    """

    def __init__(self, source: ExogenousSource, specs: dict[str, FeatureSpec]) -> None:
        self._source = source
        self._specs = specs

    def _feature_plan(self) -> list[tuple[str, str, str, int]]:
        """Ordered, deterministic list of ``(feature_name, variable, kind, param)``."""
        plan: list[tuple[str, str, str, int]] = []
        for name, spec in self._specs.items():
            plan += [(f"{name}_lag{k}", name, "lag", k) for k in spec.lags]
            plan += [(f"{name}_roll{w}", name, "roll", w) for w in spec.rolling_means]
            plan += [(f"{name}_diff{k}", name, "diff", k) for k in spec.diffs]
        return plan

    def build_asof(self, asof: pd.Timestamp) -> pd.Series:
        snapshots = {
            name: as_of_snapshot(self._source.vintages(name), asof) for name in self._specs
        }
        values: dict[str, float] = {}
        for feat_name, var, kind, param in self._feature_plan():
            snap = snapshots[var]
            if kind == "lag":
                values[feat_name] = lag_feature(snap, param)
            elif kind == "roll":
                values[feat_name] = rolling_mean_feature(snap, param)
            else:  # diff
                values[feat_name] = diff_feature(snap, param)
        return pd.Series(values, dtype=float)

    def build_panel(self, decision_index: pd.DatetimeIndex) -> pd.DataFrame:
        columns = [name for name, _, _, _ in self._feature_plan()]
        rows = [self.build_asof(t) for t in decision_index]
        return pd.DataFrame(rows, index=decision_index, columns=columns)


__all__ = [
    "DEFAULT_PUBLICATION_LAGS",
    "LookAheadError",
    "as_of_snapshot",
    "from_lagged_series",
    "assert_point_in_time",
    "lag_feature",
    "rolling_mean_feature",
    "diff_feature",
    "FeatureSpec",
    "PointInTimeFeatureBuilder",
    # convenience re-exports
    "KNOWLEDGE_TS",
    "VALUE",
    "VALUE_TS",
]
