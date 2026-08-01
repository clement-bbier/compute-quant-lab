"""Tests-first for quoting and the orchestrator (``futures`` + ``protocols``).

Covers P06 spec §6: (d) the ``simulated`` flag is MANDATORY (a test MUST fail if
it's missing), and the orchestrator produces a quote that is always simulated,
consistent with the carry core. Also checks the DI contract (``runtime_checkable``).
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
    # Real/simulated boundary: a quote cannot be constructed without explicitly
    # declaring that it is simulated — the guarantee is enforced by the type.
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
    assert quote.simulated is True  # futures not listed


def test_pricer_computes_forward_basis_and_implied_yield() -> None:
    pricer = CarryFuturesPricer(CostOfCarryModel(rate=RATE, convenience_yield=YIELD), rate=RATE)
    quote = pricer.price(SPOT, TAU)

    expected_forward = carry_forward(SPOT, RATE, YIELD, TAU)
    assert quote.spot == SPOT
    assert quote.maturity_years == TAU
    assert quote.forward == pytest.approx(expected_forward)
    assert quote.basis == pytest.approx(expected_forward - SPOT)
    # The pricer infers y from the forward; for exogenous carry it returns y.
    assert quote.convenience_yield == pytest.approx(YIELD)
    assert quote.model_name == "cost_of_carry"


def test_pricer_quote_carries_analytic_sensitivities() -> None:
    pricer = CarryFuturesPricer(CostOfCarryModel(rate=RATE, convenience_yield=YIELD), rate=RATE)
    quote = pricer.price(SPOT, TAU)
    assert quote.sensitivities.d_forward_d_rate == pytest.approx(quote.forward * TAU)
    assert quote.sensitivities.d_forward_d_yield == pytest.approx(-quote.forward * TAU)
