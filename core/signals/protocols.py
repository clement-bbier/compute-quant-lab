"""Signal layer contracts (reusable foundation — SOLID / Dependency Inversion).

``core.signals`` promotes the *reusable signal producers* (mean-reversion P02, futures basis
P06, ML P09) behind a common interface. The P10 desk — and any future optimiser — depends on
this ``Protocol``, never on a concrete implementation (DIP / OCP): plugging in a new signal
does not change the consumer.

P08 compatibility: ``signal(view) -> float`` is exactly the signature of the ``Strategy``
Protocol in ``core.backtest`` — so a producer is **directly backtestable** by the engine. The
output is a **normalised directional view** in ``[-1, 1]`` (not a final position: the desk
sizes it through its own risk weighting).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from core.backtest.protocols import PointInTimeView


@dataclass(frozen=True)
class SignalProvenance:
    """Origin of a signal: real vs simulated. ``simulated`` is **mandatory** (no default).

    The real/simulated boundary is non-negotiable (rule ``forward-real-simulated``): it is
    impossible to forget to label a signal — a test fails if the flag is missing.
    """

    name: str
    simulated: bool


@runtime_checkable
class SignalProducer(Protocol):
    """Source of a point-in-time directional signal, labelled by its provenance.

    At each time ``t``, returns a directional view ``s in [-1, 1]`` computed from data
    ``<= t`` (consumes the P08 ``PointInTimeView`` / ``GuardedView``). ``Strategy``-compatible.
    """

    name: str
    provenance: SignalProvenance

    def signal(self, view: PointInTimeView) -> float: ...


def clip_unit(value: float) -> float:
    """Clip a directional view to the ``[-1, 1]`` interval."""
    return max(-1.0, min(1.0, value))


__all__ = ["SignalProvenance", "SignalProducer", "clip_unit"]
