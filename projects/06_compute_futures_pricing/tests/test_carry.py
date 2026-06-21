"""Tests-first du cœur cost-of-carry (``core.pricing.derivatives.carry``).

Couvre la spec P06 §6 : (a) forward sur params connus, (b) base = F − S,
(c) convergence F(τ=0) = S, et le round-trip du convenience yield implicite —
le pivot du modèle (y non observable, inféré depuis la forward).
"""

from __future__ import annotations

import math

import pytest

from core.pricing.derivatives.carry import (
    CostOfCarryModel,
    carry_forward,
    carry_sensitivities,
    implied_convenience_yield,
)

# Paramètres de référence (annualisés). spot en $/GPU·h.
SPOT = 2.50
RATE = 0.04
YIELD = 0.015
TAU = 0.5  # 6 mois


def test_carry_forward_matches_closed_form() -> None:
    # F = S·e^{(r−y)τ} = 2.50 · e^{(0.04−0.015)·0.5}
    expected = SPOT * math.exp((RATE - YIELD) * TAU)
    assert carry_forward(SPOT, RATE, YIELD, TAU) == pytest.approx(expected)
    assert carry_forward(SPOT, RATE, YIELD, TAU) == pytest.approx(2.5314461, abs=1e-6)


def test_carry_forward_converges_to_spot_at_zero_maturity() -> None:
    # F(τ=0) = S exactement (propriété de convergence).
    assert carry_forward(SPOT, RATE, YIELD, 0.0) == SPOT


def test_contango_when_rate_exceeds_yield() -> None:
    # r > y ⇒ forward au-dessus du spot (base positive, marché en report).
    forward = carry_forward(SPOT, RATE, YIELD, TAU)
    basis = forward - SPOT
    assert basis > 0


def test_backwardation_when_yield_exceeds_rate() -> None:
    # y > r ⇒ forward sous le spot (base négative, déport).
    forward = carry_forward(SPOT, RATE, 0.10, TAU)
    assert forward - SPOT < 0


def test_implied_convenience_yield_round_trips() -> None:
    # Inverser la forward carry doit redonner exactement le y d'origine.
    forward = carry_forward(SPOT, RATE, YIELD, TAU)
    assert implied_convenience_yield(SPOT, forward, RATE, TAU) == pytest.approx(YIELD)


def test_implied_convenience_yield_rejects_non_positive_maturity() -> None:
    with pytest.raises(ValueError):
        implied_convenience_yield(SPOT, SPOT, RATE, 0.0)


def test_carry_sensitivities_are_analytic() -> None:
    forward = carry_forward(SPOT, RATE, YIELD, TAU)
    sens = carry_sensitivities(SPOT, RATE, YIELD, TAU)
    # ∂F/∂r = F·τ ; ∂F/∂y = −F·τ ; ∂F/∂τ = F·(r−y).
    assert sens.d_forward_d_rate == pytest.approx(forward * TAU)
    assert sens.d_forward_d_yield == pytest.approx(-forward * TAU)
    assert sens.d_forward_d_tau == pytest.approx(forward * (RATE - YIELD))


def test_cost_of_carry_model_is_simulated_and_named() -> None:
    model = CostOfCarryModel(rate=RATE, convenience_yield=YIELD)
    assert model.simulated is True  # futures non listés → toujours théorique
    assert model.name == "cost_of_carry"
    assert model.forward(SPOT, TAU) == pytest.approx(carry_forward(SPOT, RATE, YIELD, TAU))
