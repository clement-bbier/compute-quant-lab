"""Tests-first for carry ↔ P04 SIMULATED Schwartz forward consistency (spec §6e).

``P04ForwardAdapter`` (project layer) plugs P04's forward curve into the core's
``CarryModel`` contract. Checks: (1) it faithfully reproduces the P04 analytic
forward (with years→days conversion), (2) the pricer derives a quote that is
always simulated, (3) the implicit convenience yield exactly reconstructs the
Schwartz forward — this is the bridge between the cost-of-carry framework and
the P04 model.
"""

from __future__ import annotations

import pytest

# Core (package installed in editable mode).
from core.pricing.derivatives.carry import carry_forward
from core.pricing.derivatives.futures import CarryFuturesPricer, FuturesQuote
from core.pricing.derivatives.protocols import CarryModel

# Project layer + P04 package (made importable by conftest).
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
    # The adapter's forward (in years) must equal P04's forward_price (in days).
    adapter = P04ForwardAdapter(PARAMS)
    tau_years = 90.0 / DAYS_PER_YEAR
    expected = forward_price(SPOT, PARAMS, 90.0)
    assert adapter.forward(SPOT, tau_years) == pytest.approx(expected)


def test_adapter_matches_full_p04_curve_point_by_point() -> None:
    # Consistency across the entire P04 curve (analytic oracle).
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
    # The implicit yield extracted from the Schwartz forward, reinjected into carry,
    # must return exactly the P04 forward (round-trip consistency).
    tau_years = 180.0 / DAYS_PER_YEAR
    f_p04 = forward_price(SPOT, PARAMS, 180.0)
    quote = CarryFuturesPricer(P04ForwardAdapter(PARAMS), rate=RATE).price(SPOT, tau_years)
    assert quote.forward == pytest.approx(f_p04)
    reconstructed = carry_forward(SPOT, RATE, quote.convenience_yield, tau_years)
    assert reconstructed == pytest.approx(f_p04)
