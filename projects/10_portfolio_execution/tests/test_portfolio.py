"""Construction de portefeuille : pondération inverse-vol + budget de risque (test §6-a).

On prouve la formule de pondération sur des volatilités *connues* → poids attendus, puis le
plancher de vol (anti-domination d'un signal à vol quasi nulle) et l'écrêtage du levier brut.
"""

from __future__ import annotations

import numpy as np
import pytest

from portfolio import (
    ERCScheme,
    InverseVolScheme,
    PortfolioConstructor,
    inverse_vol_weights,
)


def test_equal_vols_give_equal_weights() -> None:
    """Volatilités égales → poids égaux (cas de symétrie)."""
    w = inverse_vol_weights(np.array([1.0, 1.0]))
    assert np.allclose(w, [0.5, 0.5])


def test_lower_vol_gets_more_weight() -> None:
    """w_i ∝ 1/σ_i : σ=[1,2] → poids [2/3, 1/3] (le signal le moins volatil pèse plus)."""
    w = inverse_vol_weights(np.array([1.0, 2.0]))
    assert np.allclose(w, [2.0 / 3.0, 1.0 / 3.0])


def test_weights_sum_to_one() -> None:
    """La pondération est entièrement investie : Σ w_i = 1."""
    w = inverse_vol_weights(np.array([0.5, 1.0, 2.0, 4.0]))
    assert pytest.approx(1.0) == w.sum()


def test_risk_budget_scales_weights() -> None:
    """Budget de risque b_i : à vols égales, b=[2,1] → poids [2/3, 1/3]."""
    w = inverse_vol_weights(np.array([1.0, 1.0]), risk_budget=np.array([2.0, 1.0]))
    assert np.allclose(w, [2.0 / 3.0, 1.0 / 3.0])


def test_inverse_vol_scheme_matches_function() -> None:
    """InverseVolScheme délègue exactement à inverse_vol_weights (pas de divergence)."""
    vols = np.array([1.0, 3.0])
    assert np.allclose(InverseVolScheme().weights(vols), inverse_vol_weights(vols))


def test_vol_floor_caps_domination() -> None:
    """Une vol quasi nulle est plancher née : elle ne rafle pas tout le poids."""
    constructor = PortfolioConstructor(vol_floor=0.5, gross_cap=1.0)
    w = constructor.weights(np.array([1e-12, 1.0]))
    # vols plancher = [0.5, 1.0] → inv = [2, 1] → [2/3, 1/3] (et non [≈1, ≈0]).
    assert np.allclose(w, [2.0 / 3.0, 1.0 / 3.0])


def test_net_position_is_weighted_sum_of_signals() -> None:
    """Position nette = Σ w_i·s_i. Signaux opposés de poids égaux → position nulle."""
    constructor = PortfolioConstructor(vol_floor=0.01, gross_cap=1.0)
    assert constructor.net_position(np.array([0.5, 0.5]), np.array([1.0, -1.0])) == 0.0
    assert constructor.net_position(np.array([0.5, 0.5]), np.array([1.0, 1.0])) == 1.0


def test_gross_cap_clips_leverage() -> None:
    """L'exposition brute est écrêtée à ±gross_cap (limite desk)."""
    constructor = PortfolioConstructor(vol_floor=0.01, gross_cap=0.5)
    assert constructor.net_position(np.array([0.5, 0.5]), np.array([1.0, 1.0])) == 0.5
    assert constructor.net_position(np.array([0.5, 0.5]), np.array([-1.0, -1.0])) == -0.5


def test_erc_scheme_is_documented_seam() -> None:
    """ERCScheme (risk-parity, palier institutionnel) est un seam OCP non encore implémenté."""
    with pytest.raises(NotImplementedError):
        ERCScheme().weights(np.array([1.0, 2.0]))
