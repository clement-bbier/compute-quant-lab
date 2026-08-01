"""Public / edge boundary — the product's **single injection point**.

The public product consumes an *injected* :class:`SignalSource`. The default
implementation (:class:`NaiveSignalSource`) is a **trivial, non-edge heuristic**: it only
looks at the current measurement. The real **calibrated timing** (the monetizable edge)
lives in ``private/`` (WP) and substitutes this ``SignalSource`` *locally*, **never
committed**. Since the product depends only on the Protocol, it is structurally
impossible to leak the edge in the clear (mypy guards the boundary).

Real/simulated discipline borrowed from ``core.signals`` (rule ``forward-real-simulated``)
but **decoupled**: the product layer does not pull in the backtest engine (Rust core).
Here ``simulated=True`` means "non-edge heuristic recommendation" — the free tier is
never mistaken for a validated signal. A calibrated edge impl would carry ``simulated=False``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable

from views import MarketView


class Action(Enum):
    """Procurement recommendation (the "what to do now")."""

    WAIT = "wait"
    RENT_NOW = "rent_now"


@dataclass(frozen=True)
class SignalProvenance:
    """Origin of a recommendation. ``simulated`` is **mandatory** (no default).

    Impossible to forget to label a recommendation: constructing it without the flag
    raises ``TypeError`` (guaranteed by a test). ``simulated=True`` ⇔ non-edge heuristic.
    """

    name: str
    simulated: bool


@dataclass(frozen=True)
class ProcurementSignal:
    """Point-in-time recommendation served by a :class:`SignalSource`.

    ``action`` is the decision; ``venue``/``reference_price`` locate the best *measured*
    offer; ``rationale`` explains the reason (auditable); ``provenance`` labels
    the origin (edge vs. heuristic).
    """

    action: Action
    gpu_model: str
    venue: str
    reference_price: float
    rationale: str
    provenance: SignalProvenance


@runtime_checkable
class SignalSource(Protocol):
    """Source of a procurement recommendation — **the injection point**.

    A single method: from a point-in-time :class:`~views.MarketView`, produce
    a :class:`ProcurementSignal`. The public impl is naive; the private edge substitutes it.
    """

    name: str

    def assess(self, market: MarketView) -> ProcurementSignal: ...


@dataclass(frozen=True)
class NaiveSignalSource:
    """Default public impl — trivial heuristic, **no edge**.

    ``RENT_NOW`` iff the cheapest venue is *strictly* below the cross-venue median
    (a real gap worth capturing exists); otherwise ``WAIT`` (no gap → nothing urgent). No
    calibrated threshold, no timing information: the real edge lives in ``private/`` (WP).
    """

    name: str = "naive_public"

    def assess(self, market: MarketView) -> ProcurementSignal:
        cheapest = market.cheapest
        has_spread = cheapest.rate < market.median_rate
        action = Action.RENT_NOW if has_spread else Action.WAIT
        rationale = (
            f"public heuristic: {cheapest.source} at {cheapest.rate:.2f} $/GPU·h "
            f"{'below' if has_spread else 'at the level of'} the cross-venue median "
            f"({market.median_rate:.2f}). Calibrated timing = premium (private edge)."
        )
        return ProcurementSignal(
            action=action,
            gpu_model=market.gpu_model,
            venue=cheapest.source,
            reference_price=cheapest.rate,
            rationale=rationale,
            provenance=SignalProvenance(name=self.name, simulated=True),
        )
