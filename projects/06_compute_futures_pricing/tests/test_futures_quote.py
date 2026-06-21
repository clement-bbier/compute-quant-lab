"""Tests-first de la cotation et de l'orchestrateur (``futures`` + ``protocols``).

Couvre la spec P06 §6 : (d) le drapeau ``simulated`` est OBLIGATOIRE (un test DOIT
échouer s'il manque), et l'orchestrateur produit une cotation toujours simulée,
cohérente avec le cœur carry. Vérifie aussi le contrat DI (``runtime_checkable``).
"""

from __future__ import annotations

import pytest

from core.pricing.derivatives.carry import CostOfCarryModel, carry_forward
from core.pricing.derivatives.futures import CarryFuturesPricer, FuturesQuote
from core.pricing.derivatives.protocols import CarryModel, FuturesPricer

SPOT = 2.50
RATE = 0.04
YIELD = 0.015
TAU = 0.5


def test_futures_quote_requires_simulated_flag() -> None:
    # Frontière réel/simulé : impossible de construire une cotation sans déclarer
    # explicitement qu'elle est simulée — la garantie est portée par le type.
    with pytest.raises(TypeError):
        FuturesQuote(  # type: ignore[call-arg]
            spot=SPOT,
            forward=2.53,
            maturity_years=TAU,
            basis=0.03,
            rate=RATE,
            convenience_yield=YIELD,
            model_name="cost_of_carry",
            sensitivities=None,  # type: ignore[arg-type]
        )


def test_cost_of_carry_model_satisfies_carry_model_protocol() -> None:
    assert isinstance(CostOfCarryModel(), CarryModel)  # runtime_checkable


def test_pricer_satisfies_futures_pricer_protocol() -> None:
    assert isinstance(CarryFuturesPricer(CostOfCarryModel()), FuturesPricer)


def test_pricer_output_is_always_simulated() -> None:
    pricer = CarryFuturesPricer(CostOfCarryModel(rate=RATE, convenience_yield=YIELD), rate=RATE)
    quote = pricer.price(SPOT, TAU)
    assert isinstance(quote, FuturesQuote)
    assert quote.simulated is True  # futures non listés


def test_pricer_computes_forward_basis_and_implied_yield() -> None:
    pricer = CarryFuturesPricer(CostOfCarryModel(rate=RATE, convenience_yield=YIELD), rate=RATE)
    quote = pricer.price(SPOT, TAU)

    expected_forward = carry_forward(SPOT, RATE, YIELD, TAU)
    assert quote.spot == SPOT
    assert quote.maturity_years == TAU
    assert quote.forward == pytest.approx(expected_forward)
    assert quote.basis == pytest.approx(expected_forward - SPOT)
    # Le pricer infère y depuis la forward ; pour le carry exogène il redonne y.
    assert quote.convenience_yield == pytest.approx(YIELD)
    assert quote.model_name == "cost_of_carry"


def test_pricer_quote_carries_analytic_sensitivities() -> None:
    pricer = CarryFuturesPricer(CostOfCarryModel(rate=RATE, convenience_yield=YIELD), rate=RATE)
    quote = pricer.price(SPOT, TAU)
    assert quote.sensitivities.d_forward_d_rate == pytest.approx(quote.forward * TAU)
    assert quote.sensitivities.d_forward_d_yield == pytest.approx(-quote.forward * TAU)
