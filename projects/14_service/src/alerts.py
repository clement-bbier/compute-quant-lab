"""Alert engine — PoC skeleton with **a single injection point**.

The engine consumes an injected :class:`~signal_iface.SignalSource`, derives a
:class:`~signal_iface.ProcurementSignal` from it, then evaluates **declarative rules**:

- :class:`PriceBelow` — "price below a threshold": **pure public**, requires no edge;
- :class:`ActionIs` — "the recommendation is RENT_NOW": driven by the injected source
  (naive public by default, or the private edge substituted locally).

Assumed skeleton: **delivery** (email / webhook) is not implemented in the PoC. The
provided :class:`Notifier` implementations are stubs (in-memory for tests/dashboard, log for
monitoring); wiring up a real channel = a new Protocol implementation (OCP), without touching
the engine. Everything is **deterministic and point-in-time**: an event's timestamp is
``market.as_of`` (no hidden ``datetime.now()``).
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass, field
from typing import Protocol, Sequence, runtime_checkable

from core.utils.logging import get_logger
from signal_iface import Action, ProcurementSignal, SignalSource
from views import MarketView


@runtime_checkable
class Rule(Protocol):
    """Trigger condition, evaluated on a :class:`ProcurementSignal`."""

    @property
    def label(self) -> str:
        """Auditable label of the rule (traced in the event)."""
        ...

    def matches(self, signal: ProcurementSignal) -> bool:
        """True if the rule triggers for ``signal``."""
        ...


@dataclass(frozen=True)
class PriceBelow:
    """Pure public rule: triggers if the reference price ``<= threshold``."""

    threshold: float

    @property
    def label(self) -> str:
        return f"price<={self.threshold}"

    def matches(self, signal: ProcurementSignal) -> bool:
        return signal.reference_price <= self.threshold


@dataclass(frozen=True)
class ActionIs:
    """Rule driven by the injected source: triggers if ``action`` matches."""

    action: Action

    @property
    def label(self) -> str:
        return f"action={self.action.value}"

    def matches(self, signal: ProcurementSignal) -> bool:
        return signal.action is self.action


@dataclass(frozen=True)
class AlertEvent:
    """Triggered alert — auditable snapshot of what fired."""

    gpu_model: str
    venue: str
    reference_price: float
    action: Action
    rule_label: str
    fired_at: dt.datetime


@runtime_checkable
class Notifier(Protocol):
    """Notification channel (PoC stub: in-memory, log; real = new impl, OCP)."""

    def notify(self, event: AlertEvent) -> None:
        """Emits ``event`` on the channel."""
        ...


@dataclass
class InMemoryNotifier:
    """Stub: accumulates events in memory (tests, dashboard)."""

    events: list[AlertEvent] = field(default_factory=list)

    def notify(self, event: AlertEvent) -> None:
        self.events.append(event)


@dataclass
class LoggingNotifier:
    """Stub: logs the alert (``core.utils.logging``, never ``print``)."""

    logger: logging.Logger = field(default_factory=lambda: get_logger("ws.alerts"))

    def notify(self, event: AlertEvent) -> None:
        self.logger.info(
            "ALERT [%s] %s: %s at %.2f $/GPU·h (%s)",
            event.rule_label,
            event.gpu_model,
            event.venue,
            event.reference_price,
            event.action.value,
        )


@dataclass
class AlertEngine:
    """Evaluates rules against the recommendation of an injected :class:`SignalSource`.

    Parameters
    ----------
    source
        Recommendation producer — **the injection point** (naive public by default,
        private edge substituted locally).
    notifier
        Channel for emitting triggered alerts (stub in PoC).
    """

    source: SignalSource
    notifier: Notifier

    def evaluate(
        self,
        market: MarketView,
        rules: Sequence[Rule],
        *,
        now: dt.datetime | None = None,
    ) -> list[AlertEvent]:
        """Triggers the rules satisfied for the ``market``.

        Parameters
        ----------
        market
            Point-in-time snapshot of the model (cf. :func:`views.read_market`).
        rules
            Rules to evaluate (``PriceBelow``, ``ActionIs``, …).
        now
            Timestamp of the events; default = ``market.as_of`` (deterministic, point-in-time).

        Returns
        -------
        list[AlertEvent]
            The triggered alerts (also forwarded to the ``notifier``).
        """
        signal = self.source.assess(market)
        fired_at = now if now is not None else market.as_of
        fired: list[AlertEvent] = []
        for rule in rules:
            if rule.matches(signal):
                event = AlertEvent(
                    gpu_model=signal.gpu_model,
                    venue=signal.venue,
                    reference_price=signal.reference_price,
                    action=signal.action,
                    rule_label=rule.label,
                    fired_at=fired_at,
                )
                self.notifier.notify(event)
                fired.append(event)
        return fired
