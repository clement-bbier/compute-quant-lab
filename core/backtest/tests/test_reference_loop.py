"""Oracle Python pur de la phase 2 (comptabilité PnL) sur cas analytiques.

C'est la *spécification exécutable* que la boucle Rust devra reproduire (parité).
"""

from __future__ import annotations

import numpy as np

from core.backtest.reference_loop import accumulate


def test_accumulate_long_one_unit_zero_cost_tracks_price_returns():
    prices = np.array([100.0, 110.0, 99.0], dtype=np.float64)
    positions = np.array([1.0, 1.0, 1.0], dtype=np.float64)  # toujours long 1
    returns, n_trades = accumulate(positions, prices, fees_bps=0.0, slippage_bps=0.0)
    # t0 : entrée, prev_pos=0, pas de mouvement de marché -> 0
    assert returns[0] == 0.0
    # t1 : prev_pos=1, marché +10 % -> +0.10
    assert np.isclose(returns[1], 0.10)
    # t2 : prev_pos=1, marché 99/110-1
    assert np.isclose(returns[2], 99.0 / 110.0 - 1.0)
    assert n_trades == 1  # une seule entrée à t0


def test_accumulate_charges_entry_and_exit_costs():
    prices = np.array([100.0, 100.0], dtype=np.float64)  # marché plat
    positions = np.array([1.0, 0.0], dtype=np.float64)  # entre puis sort
    returns, n_trades = accumulate(positions, prices, fees_bps=10.0, slippage_bps=0.0)
    # entrée +1 puis sortie -1, 10 bps sur |delta|=1 -> -0.001 chaque
    assert np.isclose(returns[0], -0.001)
    assert np.isclose(returns[1], -0.001)
    assert n_trades == 2


def test_accumulate_flat_position_yields_zero():
    prices = np.array([100.0, 120.0, 90.0], dtype=np.float64)
    positions = np.zeros(3, dtype=np.float64)  # jamais investi
    returns, n_trades = accumulate(positions, prices, fees_bps=10.0, slippage_bps=5.0)
    np.testing.assert_array_equal(returns, np.zeros(3))
    assert n_trades == 0
