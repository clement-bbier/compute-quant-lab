"""Deterministic signal mocks (PoC placeholders) + re-export of the canonical contract.

The ``SignalProducer`` contract and provenance now live in ``core.signals`` (foundation
promoted by P12); they are **re-exported** here for backward compatibility. The **real**
producers (mean-reversion P02, futures basis P06, ML P09) are in ``core.signals`` and are
wired into the desk via ``run_desk.REAL_PRODUCERS`` without the desk changing any code (OCP).

The mocks below remain for the desk's regression tests (analytical cases, anti
look-ahead, DI): three **stateless** stubs, labeled simulated — ``ConstantMock`` (constant
carry), ``MeanReversionMock`` (fades the deviation, P02-style), ``MomentumMock`` (follows the
trend, P06/P09-style). Their economic relevance is out of scope.
"""

from __future__ import annotations

from core.backtest import PointInTimeView
from core.signals import SignalProducer

from provenance import SignalProvenance

__all__ = [
    "SignalProducer",
    "ConstantMock",
    "MeanReversionMock",
    "MomentumMock",
]


def _clip_unit(value: float) -> float:
    """Clips a directional view to the [-1, 1] interval."""
    return max(-1.0, min(1.0, value))


def _zscore(view: PointInTimeView, lookback: int) -> float | None:
    """Z-score of the current value over the ``≤ t`` window of size ``lookback``.

    Returns ``None`` if the history is too short (< ``lookback``) or if the standard deviation is
    zero (flat window): in these cases, no signal is defined → the caller stays neutral.
    """
    history = view.history()
    if history.size < lookback:
        return None
    recent = history[-lookback:]
    std = float(recent.std(ddof=1))
    if std == 0.0:
        return None
    return (view.latest() - float(recent.mean())) / std


class ConstantMock:
    """Constant directional signal (placeholder for a carry bias). ``value`` clipped to [-1, 1]."""

    def __init__(self, value: float, *, name: str = "constant_mock") -> None:
        self._value = _clip_unit(value)
        self.name = name
        self.provenance = SignalProvenance(name=name, simulated=True)

    def signal(self, view: PointInTimeView) -> float:
        """Returns the constant value, regardless of the timestamp (but via the guarded view)."""
        return self._value


class MeanReversionMock:
    """Fades the deviation: ``s = clip(-z, -1, 1)`` (P02 placeholder). Stateless → deterministic."""

    def __init__(self, lookback: int, *, name: str = "mean_reversion_mock") -> None:
        if lookback < 2:
            raise ValueError(f"lookback ({lookback}) must be ≥ 2 (otherwise std is undefined).")
        self.lookback = lookback
        self.name = name
        self.provenance = SignalProvenance(name=name, simulated=True)

    def signal(self, view: PointInTimeView) -> float:
        """Target directional position at t: sell above the mean, buy below it."""
        z = _zscore(view, self.lookback)
        return 0.0 if z is None else _clip_unit(-z)


class MomentumMock:
    """Follows the trend: ``s = clip(z, -1, 1)`` (P06/P09 placeholder). Opposite of mean-reversion."""

    def __init__(self, lookback: int, *, name: str = "momentum_mock") -> None:
        if lookback < 2:
            raise ValueError(f"lookback ({lookback}) must be ≥ 2 (otherwise std is undefined).")
        self.lookback = lookback
        self.name = name
        self.provenance = SignalProvenance(name=name, simulated=True)

    def signal(self, view: PointInTimeView) -> float:
        """Target directional position at t: buy when price is above its mean."""
        z = _zscore(view, self.lookback)
        return 0.0 if z is None else _clip_unit(z)
