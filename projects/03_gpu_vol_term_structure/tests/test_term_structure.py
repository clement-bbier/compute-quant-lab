"""Tests of term structure analysis (slope, curvature, classification).

Synthetic curves with known shape: contango (increasing), backwardation
(decreasing), flat, convex. We check the sign of the slope, the classification
and the sign of the curvature.
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
    # butterfly F_short - 2 F_mid + F_long = 2.10 - 2*2.00 + 2.10 = 0.20 > 0
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
