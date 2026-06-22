"""Tests du moteur d'alerte (règles déclaratives + point d'injection unique)."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from conftest import AS_OF

from core.ingestion.protocols import VenueRate
from alerts import (
    ActionIs,
    AlertEngine,
    InMemoryNotifier,
    LoggingNotifier,
    Notifier,
    PriceBelow,
)
from signal_iface import Action, ProcurementSignal, SignalProvenance
from views import MarketView


def _signal(*, action: Action = Action.RENT_NOW, price: float = 2.0) -> ProcurementSignal:
    return ProcurementSignal(
        action=action,
        gpu_model="H100",
        venue="vastai",
        reference_price=price,
        rationale="test",
        provenance=SignalProvenance("fake", simulated=True),
    )


@dataclass
class FakeSource:
    """SignalSource de test : rend une recommandation fixée (ignore le marché)."""

    signal: ProcurementSignal
    name: str = "fake"

    def assess(self, market: MarketView) -> ProcurementSignal:
        return self.signal


def _market() -> MarketView:
    venues = (VenueRate(source="vastai", rate=2.0, availability=1, snapshotted_at=AS_OF),)
    return MarketView(as_of=AS_OF, gpu_model="H100", venues=venues, index_price=2.0, method="t")


def test_price_below_rule_matches_threshold():
    assert PriceBelow(2.5).matches(_signal(price=2.0)) is True
    assert PriceBelow(1.5).matches(_signal(price=2.0)) is False


def test_action_rule_matches_action():
    assert ActionIs(Action.RENT_NOW).matches(_signal(action=Action.RENT_NOW)) is True
    assert ActionIs(Action.RENT_NOW).matches(_signal(action=Action.WAIT)) is False


def test_engine_fires_and_notifies_on_match():
    notifier = InMemoryNotifier()
    engine = AlertEngine(source=FakeSource(_signal(price=2.0)), notifier=notifier)
    events = engine.evaluate(_market(), [PriceBelow(2.5)])
    assert len(events) == 1
    assert notifier.events == events
    assert events[0].reference_price == pytest.approx(2.0)
    assert events[0].venue == "vastai"


def test_engine_silent_when_no_rule_matches():
    notifier = InMemoryNotifier()
    engine = AlertEngine(source=FakeSource(_signal(price=2.0)), notifier=notifier)
    events = engine.evaluate(_market(), [PriceBelow(1.0)])
    assert events == []
    assert notifier.events == []


def test_engine_action_rule_reacts_to_injected_signal():
    # L'edge injecté pilote l'alerte d'action : RENT_NOW déclenche, WAIT non.
    waiting = AlertEngine(FakeSource(_signal(action=Action.WAIT)), InMemoryNotifier())
    assert waiting.evaluate(_market(), [ActionIs(Action.RENT_NOW)]) == []

    notifier = InMemoryNotifier()
    renting = AlertEngine(FakeSource(_signal(action=Action.RENT_NOW)), notifier)
    assert len(renting.evaluate(_market(), [ActionIs(Action.RENT_NOW)])) == 1


def test_event_fired_at_defaults_to_market_as_of():
    # Déterministe et point-in-time : pas de dt.now() caché.
    engine = AlertEngine(FakeSource(_signal()), InMemoryNotifier())
    events = engine.evaluate(_market(), [PriceBelow(99.0)])
    assert events[0].fired_at == AS_OF


def test_logging_notifier_does_not_raise():
    engine = AlertEngine(FakeSource(_signal()), LoggingNotifier())
    assert len(engine.evaluate(_market(), [PriceBelow(99.0)])) == 1


def test_in_memory_notifier_satisfies_protocol():
    assert isinstance(InMemoryNotifier(), Notifier)
