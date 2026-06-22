"""DI prouvée : le produit tourne **sans** l'edge privé, et l'edge est substituable.

Garde anti-fuite incluse : aucune source du produit ne référence ``private/``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from conftest import AS_OF

from alerts import ActionIs, AlertEngine, InMemoryNotifier, PriceBelow
from signal_iface import Action, NaiveSignalSource, ProcurementSignal, SignalProvenance
from views import MarketView, read_market

_SRC = Path(__file__).resolve().parents[1] / "src"


def test_full_pipeline_runs_with_public_default_only(store, as_of):
    # Cold store -> mesure -> source NAÏVE par défaut -> alerte : aucun edge requis.
    market = read_market(store, as_of, "H100")
    engine = AlertEngine(source=NaiveSignalSource(), notifier=InMemoryNotifier())
    events = engine.evaluate(market, [PriceBelow(2.5), ActionIs(Action.RENT_NOW)])
    assert len(events) >= 1
    # La recommandation servie est bien l'heuristique non-edge (free tier).
    signal = NaiveSignalSource().assess(market)
    assert signal.provenance.simulated is True


def test_injection_point_accepts_substituted_edge_source():
    # Une source "edge-like" (simulated=False) se substitue SANS modifier le produit.
    @dataclass
    class FakeEdgeSource:
        name: str = "edge_like"

        def assess(self, market: MarketView) -> ProcurementSignal:
            return ProcurementSignal(
                action=Action.RENT_NOW,
                gpu_model=market.gpu_model,
                venue="calibrated",
                reference_price=market.cheapest.rate,
                rationale="edge",
                provenance=SignalProvenance("edge_like", simulated=False),
            )

    from core.ingestion.protocols import VenueRate

    market = MarketView(
        as_of=AS_OF,
        gpu_model="H100",
        venues=(VenueRate(source="vastai", rate=2.0, availability=1, snapshotted_at=AS_OF),),
        index_price=2.0,
        method="t",
    )
    engine = AlertEngine(source=FakeEdgeSource(), notifier=InMemoryNotifier())
    events = engine.evaluate(market, [ActionIs(Action.RENT_NOW)])
    assert len(events) == 1
    assert events[0].venue == "calibrated"


def test_product_sources_never_import_private_edge():
    # Garde-fou frontière : aucun edge en clair / import de private dans le produit.
    forbidden = ("import private", "from private", "private.procurement", "private.strategies")
    for path in _SRC.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{path.name} référence l'edge privé : {token!r}"
