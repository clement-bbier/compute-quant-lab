"""Explicit cost model (fees + slippage) — an alpha that dies after costs is no alpha."""

from __future__ import annotations

import pytest

from core.backtest.costs import LinearCostModel
from core.backtest.protocols import Trade


def test_linear_cost_is_bps_of_notional():
    model = LinearCostModel(fees_bps=10.0, slippage_bps=0.0)
    # +1 unit at 100 -> notional 100 -> 10 bps = 0.10 €
    assert model.cost(Trade(t=1, delta_position=1.0, price=100.0)) == pytest.approx(0.10)


def test_linear_cost_includes_slippage_and_uses_abs_notional():
    model = LinearCostModel(fees_bps=10.0, slippage_bps=5.0)
    # sale of 2 units at 50 -> |notional|=100 -> 15 bps = 0.15 €
    assert model.cost(Trade(t=3, delta_position=-2.0, price=50.0)) == pytest.approx(0.15)


def test_zero_delta_costs_nothing():
    model = LinearCostModel(fees_bps=10.0, slippage_bps=5.0)
    assert model.cost(Trade(t=2, delta_position=0.0, price=100.0)) == 0.0
