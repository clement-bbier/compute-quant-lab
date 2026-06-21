"""Tests de la courbe forward simulée (Schwartz un-facteur).

Couvre les invariants attendus (§6 du cadrage P04) : convergence vers le spot à
l'échéance 0, monotonie contango/backwardation, flag ``simulated`` obligatoire, et
parité moteur Rust ↔ oracle Python (skippée si la crate n'est pas buildée).
"""

from __future__ import annotations

import pytest

from forward.models import Curve, SchwartzParams
from forward.oracle import PythonMonteCarloForward, SchwartzAnalyticForward, forward_price

# spot < theta -> contango (courbe croissante)
PARAMS_CONTANGO = SchwartzParams(kappa=0.05, theta=3.0, sigma=0.2)
# spot > theta, faible vol -> backwardation (courbe décroissante)
PARAMS_BACKWARD = SchwartzParams(kappa=0.05, theta=1.0, sigma=0.01)
MATURITIES = [0.0, 30.0, 90.0, 180.0, 360.0]


def test_curve_requires_simulated_flag() -> None:
    # `simulated` n'a pas de valeur par défaut : l'omettre est une erreur de type.
    with pytest.raises(TypeError):
        Curve(spot=2.0, points=(), model_name="x", params=PARAMS_CONTANGO)  # type: ignore[call-arg]


def test_curve_is_flagged_simulated() -> None:
    curve = SchwartzAnalyticForward().simulate(2.0, PARAMS_CONTANGO, MATURITIES)
    assert curve.simulated is True
    assert curve.model_name == "schwartz_analytic"


def test_forward_converges_to_spot_at_zero() -> None:
    curve = SchwartzAnalyticForward().simulate(2.0, PARAMS_CONTANGO, MATURITIES)
    assert curve.prices[0] == pytest.approx(2.0)


def test_forward_price_helper_is_spot_at_zero() -> None:
    assert forward_price(2.5, PARAMS_CONTANGO, 0.0) == pytest.approx(2.5)


def test_forward_monotone_increasing_in_contango() -> None:
    prices = SchwartzAnalyticForward().simulate(2.0, PARAMS_CONTANGO, MATURITIES).prices
    assert all(b > a for a, b in zip(prices, prices[1:]))  # strictement croissante
    assert prices[-1] < PARAMS_CONTANGO.long_run_forward  # tend vers le niveau de long terme


def test_forward_monotone_decreasing_in_backwardation() -> None:
    prices = SchwartzAnalyticForward().simulate(2.0, PARAMS_BACKWARD, MATURITIES).prices
    assert all(b < a for a, b in zip(prices, prices[1:]))  # strictement décroissante


def test_python_mc_matches_analytic() -> None:
    spot, maturities = 2.0, [0.0, 30.0, 90.0]
    analytic = SchwartzAnalyticForward().simulate(spot, PARAMS_CONTANGO, maturities)
    mc = PythonMonteCarloForward(n_paths=200_000, seed=7).simulate(spot, PARAMS_CONTANGO, maturities)
    for f_analytic, f_mc in zip(analytic.prices, mc.prices):
        assert f_mc == pytest.approx(f_analytic, rel=0.02)
    assert mc.simulated is True


def test_rust_python_parity() -> None:
    # Skippé tant que la crate Rust n'est pas buildée (maturin develop).
    pytest.importorskip("forward_engine")
    from forward.engine import RustMonteCarloForward

    spot = 2.0
    maturities = [0.0, 30.0, 90.0, 180.0]
    analytic = SchwartzAnalyticForward().simulate(spot, PARAMS_CONTANGO, maturities)
    rust = RustMonteCarloForward(n_paths=200_000, seed=42).simulate(spot, PARAMS_CONTANGO, maturities)

    for f_analytic, f_rust in zip(analytic.prices, rust.prices):
        assert f_rust == pytest.approx(f_analytic, rel=0.02)
    assert rust.simulated is True
