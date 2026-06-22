"""Moteur d'alerte — squelette PoC avec **un seul point d'injection**.

Le moteur consomme un :class:`~signal_iface.SignalSource` (injecté), en tire une
:class:`~signal_iface.ProcurementSignal`, puis évalue des **règles déclaratives** :

- :class:`PriceBelow` — « prix sous un seuil » : **publique pure**, ne requiert aucun edge ;
- :class:`ActionIs` — « la reco vaut RENT_NOW » : pilotée par la source injectée (naïve
  publique par défaut, ou l'edge privé substitué localement).

Squelette assumé : la **livraison** (email / webhook) n'est pas implémentée en PoC. Les
:class:`Notifier` fournis sont des stubs (mémoire pour les tests/dashboard, log pour le
suivi) ; brancher un canal réel = nouvelle implémentation du Protocol (OCP), sans toucher
au moteur. Tout est **déterministe et point-in-time** : l'horodatage d'un événement est
``market.as_of`` (pas de ``datetime.now()`` caché).
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
    """Condition de déclenchement, évaluée sur une :class:`ProcurementSignal`."""

    @property
    def label(self) -> str:
        """Étiquette auditable de la règle (tracée dans l'événement)."""
        ...

    def matches(self, signal: ProcurementSignal) -> bool:
        """Vrai si la règle déclenche pour ``signal``."""
        ...


@dataclass(frozen=True)
class PriceBelow:
    """Règle publique pure : déclenche si le prix de référence ``<= threshold``."""

    threshold: float

    @property
    def label(self) -> str:
        return f"price<={self.threshold}"

    def matches(self, signal: ProcurementSignal) -> bool:
        return signal.reference_price <= self.threshold


@dataclass(frozen=True)
class ActionIs:
    """Règle pilotée par la source injectée : déclenche si ``action`` correspond."""

    action: Action

    @property
    def label(self) -> str:
        return f"action={self.action.value}"

    def matches(self, signal: ProcurementSignal) -> bool:
        return signal.action is self.action


@dataclass(frozen=True)
class AlertEvent:
    """Alerte déclenchée — instantané auditable de ce qui a fait feu."""

    gpu_model: str
    venue: str
    reference_price: float
    action: Action
    rule_label: str
    fired_at: dt.datetime


@runtime_checkable
class Notifier(Protocol):
    """Canal de notification (stub en PoC : mémoire, log ; réel = nouvelle impl, OCP)."""

    def notify(self, event: AlertEvent) -> None:
        """Émet ``event`` sur le canal."""
        ...


@dataclass
class InMemoryNotifier:
    """Stub : accumule les événements en mémoire (tests, dashboard)."""

    events: list[AlertEvent] = field(default_factory=list)

    def notify(self, event: AlertEvent) -> None:
        self.events.append(event)


@dataclass
class LoggingNotifier:
    """Stub : journalise l'alerte (``core.utils.logging``, jamais ``print``)."""

    logger: logging.Logger = field(default_factory=lambda: get_logger("ws.alerts"))

    def notify(self, event: AlertEvent) -> None:
        self.logger.info(
            "ALERTE [%s] %s : %s à %.2f $/GPU·h (%s)",
            event.rule_label,
            event.gpu_model,
            event.venue,
            event.reference_price,
            event.action.value,
        )


@dataclass
class AlertEngine:
    """Évalue des règles sur la recommandation d'un :class:`SignalSource` injecté.

    Parameters
    ----------
    source
        Producteur de recommandation — **le point d'injection** (naïf public par défaut,
        edge privé substitué localement).
    notifier
        Canal d'émission des alertes déclenchées (stub en PoC).
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
        """Déclenche les règles satisfaites pour le marché ``market``.

        Parameters
        ----------
        market
            Photo point-in-time du modèle (cf. :func:`views.read_market`).
        rules
            Règles à évaluer (``PriceBelow``, ``ActionIs``, …).
        now
            Horodatage des événements ; défaut = ``market.as_of`` (déterministe, point-in-time).

        Returns
        -------
        list[AlertEvent]
            Les alertes déclenchées (aussi transmises au ``notifier``).
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
