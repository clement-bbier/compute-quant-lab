"""Tests-first de la cohérence carry ↔ forward Schwartz SIMULÉE de P04 (spec §6e).

``P04ForwardAdapter`` (couche projet) branche la courbe forward de P04 dans le
contrat ``CarryModel`` du cœur. On vérifie : (1) il reproduit fidèlement la forward
analytique P04 (avec conversion années→jours), (2) le pricer en tire une cotation
toujours simulée, (3) le convenience yield implicite reconstruit exactement la
forward Schwartz — c'est le pont entre le cadre cost-of-carry et le modèle P04.
"""

from __future__ import annotations

import pytest

# Cœur (paquet installé en editable).
from core.pricing.derivatives.carry import carry_forward
from core.pricing.derivatives.futures import CarryFuturesPricer, FuturesQuote
from core.pricing.derivatives.protocols import CarryModel

# Couche projet + paquet P04 (rendus importables par conftest).
from forward.models import SchwartzParams
from forward.oracle import SchwartzAnalyticForward, forward_price
from p04_forward_adapter import DAYS_PER_YEAR, P04ForwardAdapter

SPOT = 2.50
RATE = 0.04
PARAMS = SchwartzParams(kappa=0.05, theta=2.0, sigma=0.3)


def test_adapter_satisfies_carry_model_protocol() -> None:
    adapter = P04ForwardAdapter(PARAMS)
    assert isinstance(adapter, CarryModel)  # runtime_checkable
    assert adapter.simulated is True
    assert adapter.name == "schwartz_p04"


def test_adapter_reproduces_p04_analytic_forward() -> None:
    # La forward de l'adapter (en années) doit égaler forward_price P04 (en jours).
    adapter = P04ForwardAdapter(PARAMS)
    tau_years = 90.0 / DAYS_PER_YEAR
    expected = forward_price(SPOT, PARAMS, 90.0)
    assert adapter.forward(SPOT, tau_years) == pytest.approx(expected)


def test_adapter_matches_full_p04_curve_point_by_point() -> None:
    # Cohérence sur toute la courbe P04 (oracle analytique).
    maturities_days = [30.0, 90.0, 180.0, 360.0]
    curve = SchwartzAnalyticForward().simulate(SPOT, PARAMS, maturities_days)
    adapter = P04ForwardAdapter(PARAMS)
    for tau_days, forward in zip(curve.maturities, curve.prices):
        assert adapter.forward(SPOT, tau_days / DAYS_PER_YEAR) == pytest.approx(forward)


def test_pricer_on_p04_forward_is_simulated() -> None:
    quote = CarryFuturesPricer(P04ForwardAdapter(PARAMS), rate=RATE).price(
        SPOT, 90.0 / DAYS_PER_YEAR
    )
    assert isinstance(quote, FuturesQuote)
    assert quote.simulated is True
    assert quote.model_name == "schwartz_p04"


def test_implied_yield_reconstructs_p04_forward() -> None:
    # Le yield implicite extrait de la forward Schwartz, réinjecté dans le carry,
    # doit redonner exactement la forward P04 (cohérence du round-trip).
    tau_years = 180.0 / DAYS_PER_YEAR
    f_p04 = forward_price(SPOT, PARAMS, 180.0)
    quote = CarryFuturesPricer(P04ForwardAdapter(PARAMS), rate=RATE).price(SPOT, tau_years)
    assert quote.forward == pytest.approx(f_p04)
    reconstructed = carry_forward(SPOT, RATE, quote.convenience_yield, tau_years)
    assert reconstructed == pytest.approx(f_p04)
