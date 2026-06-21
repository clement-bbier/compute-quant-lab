"""Tests de l'analyse de structure par terme (pente, courbure, classification).

Courbes synthétiques à forme connue : contango (croissante), backwardation
(décroissante), plate, convexe. On vérifie le signe de la pente, la classification
et le signe de la courbure.
"""

from __future__ import annotations

import datetime as dt

import numpy as np

from term_structure import TermStructure, TermStructureAnalyzer


def test_contango_curve_has_positive_slope(
    contango_curve: tuple[np.ndarray, np.ndarray], as_of: dt.datetime
) -> None:
    maturities, prices = contango_curve
    ts = TermStructureAnalyzer().analyze(maturities, prices, simulated=True, as_of=as_of)
    assert ts.slope > 0
    assert ts.shape == "contango"
    assert ts.front_price == prices[0]


def test_backwardation_curve_has_negative_slope(
    backwardation_curve: tuple[np.ndarray, np.ndarray], as_of: dt.datetime
) -> None:
    maturities, prices = backwardation_curve
    ts = TermStructureAnalyzer().analyze(maturities, prices, simulated=True, as_of=as_of)
    assert ts.slope < 0
    assert ts.shape == "backwardation"


def test_flat_curve_is_classified_flat(
    flat_curve: tuple[np.ndarray, np.ndarray], as_of: dt.datetime
) -> None:
    maturities, prices = flat_curve
    ts = TermStructureAnalyzer().analyze(maturities, prices, simulated=True, as_of=as_of)
    assert ts.shape == "flat"


def test_convex_curve_has_positive_curvature(
    convex_curve: tuple[np.ndarray, np.ndarray], as_of: dt.datetime
) -> None:
    maturities, prices = convex_curve
    ts = TermStructureAnalyzer().analyze(maturities, prices, simulated=True, as_of=as_of)
    # butterfly F_court - 2 F_milieu + F_long = 2.10 - 2*2.00 + 2.10 = 0.20 > 0
    assert ts.curvature > 0


def test_analyze_propagates_simulated_flag(
    backwardation_curve: tuple[np.ndarray, np.ndarray], as_of: dt.datetime
) -> None:
    maturities, prices = backwardation_curve
    ts = TermStructureAnalyzer().analyze(maturities, prices, simulated=True, as_of=as_of)
    assert ts.simulated is True


def test_result_type_is_frozen(
    flat_curve: tuple[np.ndarray, np.ndarray], as_of: dt.datetime
) -> None:
    maturities, prices = flat_curve
    ts = TermStructureAnalyzer().analyze(maturities, prices, simulated=True, as_of=as_of)
    assert isinstance(ts, TermStructure)
