"""Portfolio construction: inverse-vol weighting + risk budget (test §6-a).

We prove the weighting formula on *known* volatilities → expected weights, then the
vol floor (anti-domination by a near-zero-vol signal) and gross leverage clipping.
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
    """Equal volatilities → equal weights (symmetry case)."""
    w = inverse_vol_weights(np.array([1.0, 1.0]))
    assert np.allclose(w, [0.5, 0.5])


def test_lower_vol_gets_more_weight() -> None:
    """w_i ∝ 1/σ_i: σ=[1,2] → weights [2/3, 1/3] (the less volatile signal carries more weight)."""
    w = inverse_vol_weights(np.array([1.0, 2.0]))
    assert np.allclose(w, [2.0 / 3.0, 1.0 / 3.0])


def test_weights_sum_to_one() -> None:
    """Weighting is fully invested: Σ w_i = 1."""
    w = inverse_vol_weights(np.array([0.5, 1.0, 2.0, 4.0]))
    assert pytest.approx(1.0) == w.sum()


def test_risk_budget_scales_weights() -> None:
    """Risk budget b_i: at equal vols, b=[2,1] → weights [2/3, 1/3]."""
    w = inverse_vol_weights(np.array([1.0, 1.0]), risk_budget=np.array([2.0, 1.0]))
    assert np.allclose(w, [2.0 / 3.0, 1.0 / 3.0])


def test_inverse_vol_scheme_matches_function() -> None:
    """InverseVolScheme delegates exactly to inverse_vol_weights (no divergence)."""
    vols = np.array([1.0, 3.0])
    assert np.allclose(InverseVolScheme().weights(vols), inverse_vol_weights(vols))


def test_vol_floor_caps_domination() -> None:
    """A near-zero vol is floored: it doesn't grab all the weight."""
    constructor = PortfolioConstructor(vol_floor=0.5, gross_cap=1.0)
    w = constructor.weights(np.array([1e-12, 1.0]))
    # floored vols = [0.5, 1.0] → inv = [2, 1] → [2/3, 1/3] (not [≈1, ≈0]).
    assert np.allclose(w, [2.0 / 3.0, 1.0 / 3.0])


def test_net_position_is_weighted_sum_of_signals() -> None:
    """Net position = Σ w_i·s_i. Opposite signals with equal weight → zero position."""
    constructor = PortfolioConstructor(vol_floor=0.01, gross_cap=1.0)
    assert constructor.net_position(np.array([0.5, 0.5]), np.array([1.0, -1.0])) == 0.0
    assert constructor.net_position(np.array([0.5, 0.5]), np.array([1.0, 1.0])) == 1.0


def test_gross_cap_clips_leverage() -> None:
    """Gross exposure is clipped to ±gross_cap (desk limit)."""
    constructor = PortfolioConstructor(vol_floor=0.01, gross_cap=0.5)
    assert constructor.net_position(np.array([0.5, 0.5]), np.array([1.0, 1.0])) == 0.5
    assert constructor.net_position(np.array([0.5, 0.5]), np.array([-1.0, -1.0])) == -0.5


def test_erc_scheme_is_documented_seam() -> None:
    """ERCScheme (risk-parity, institutional tier) is an OCP seam not yet implemented."""
    with pytest.raises(NotImplementedError):
        ERCScheme().weights(np.array([1.0, 2.0]))
