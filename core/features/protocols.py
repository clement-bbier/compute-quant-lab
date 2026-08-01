"""Contracts (abstractions) of the point-in-time exogenous features.

The `PointInTimeFeatureBuilder` depends on these `Protocol` classes, never on concrete
implementations (Dependency Inversion Principle): every interchangeable exogenous data
source (gas, weather, capacity, ...) conforms to the `ExogenousSource` contract, which
makes the builders testable with fixtures and substitutable.

Data model - the *vintage* frame
-------------------------------
A macro observation carries **two** timestamps, never just one:

* ``value_ts``      — the period the figure describes ("HDD of day D");
* ``knowledge_ts``  — the instant the figure becomes *known* (published);
                      ``knowledge_ts = value_ts + publication lag``.

A revision is simply a new row with the same ``value_ts`` but a later
``knowledge_ts``. At decision instant ``t`` only the rows whose ``knowledge_ts <= t``
are visible — and, per ``value_ts``, the most recent among them. This is the only
correct defense against look-ahead on macro data.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import pandas as pd

from core.utils.types import FloatArray as FloatArray  # re-export: public alias

#: Canonical columns of a *vintage* frame (tidy, long-form).
VALUE_TS = "value_ts"
KNOWLEDGE_TS = "knowledge_ts"
VALUE = "value"
VINTAGE_COLUMNS = (VALUE_TS, KNOWLEDGE_TS, VALUE)


@runtime_checkable
class ExogenousSource(Protocol):
    """Source of exogenous variables, exposed as point-in-time *vintages*.

    Each variable is served as a long-form frame with the columns
    ``(value_ts, knowledge_ts, value)`` (index ignored), tz-aware UTC timestamps.
    The source never hides the ``knowledge_ts``: it is the caller (the builder) that
    decides what is known at ``t``.
    """

    def names(self) -> list[str]:
        """Names of the available exogenous variables."""
        ...

    def vintages(self, name: str) -> pd.DataFrame:
        """Vintage frame of ``name``: columns ``(value_ts, knowledge_ts, value)``."""
        ...


@runtime_checkable
class FeatureBuilder(Protocol):
    """Builds **point-in-time** features: at ``asof``, nothing ``> asof``."""

    def build_asof(self, asof: pd.Timestamp) -> pd.Series:
        """Feature vector known at the decision instant ``asof``."""
        ...

    def build_panel(self, decision_index: pd.DatetimeIndex) -> pd.DataFrame:
        """Panel (one row per decision instant), all features ``<= t``."""
        ...
