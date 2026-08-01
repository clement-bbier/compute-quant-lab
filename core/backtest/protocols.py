"""Backtest engine contracts (SOLID / DI).

The engine orchestrates through these abstractions: `Strategy`, `CostModel`,
`MetricsCalculator` and `PointInTimeView` are **injected**, never hard-coded.
A new kind of strategy therefore does not modify the engine (OCP).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

#: Re-exported from :mod:`core.utils.types` so the public alias name is unchanged.
from core.utils.types import FloatArray


@dataclass(frozen=True)
class Trade:
    """Position change at a given instant (what triggers a cost)."""

    t: int
    delta_position: float
    price: float


@dataclass(frozen=True)
class Ledger:
    """Phase 2 output: period-by-period accounting.

    All arrays have the same length as the price series.
    """

    returns: FloatArray
    pnl: FloatArray
    equity_curve: FloatArray
    positions: FloatArray
    n_trades: int


@dataclass(frozen=True)
class BacktestResult:
    """*Pure* result of a run: accounting + metrics + params.

    Reproducibility metadata (git SHA, run_id) does not live here:
    it is logged to MLflow by `core.backtest.tracking` (the run is replayable from
    its MLflow run_id alone). Keeps the engine free of hidden I/O.
    """

    ledger: Ledger
    metrics: dict[str, float]
    params: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class PointInTimeView(Protocol):
    """Data view restricted to the current instant t: sees only ≤ t.

    Any attempt to access an index > t must raise `LookAheadError`.
    """

    #: Current time index (strategies index relative to `t`).
    t: int

    def history(self) -> FloatArray:
        """All values known up to and including t."""
        ...

    def latest(self) -> float:
        """Value at the current instant t."""
        ...

    def at(self, i: int) -> float:
        """Value at index i; raises `LookAheadError` if i > t."""
        ...


@runtime_checkable
class Strategy(Protocol):
    """Produces a target position at t from data ≤ t only."""

    def signal(self, view: PointInTimeView) -> float: ...


@runtime_checkable
class CostModel(Protocol):
    """Cost (€) of a trade: fees + slippage."""

    def cost(self, trade: Trade) -> float: ...


@runtime_checkable
class MetricsCalculator(Protocol):
    """Computes risk metrics from a `Ledger`."""

    def compute(self, ledger: Ledger) -> dict[str, float]: ...
