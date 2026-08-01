"""Analysis of the compute forward curve's term structure (pure).

The forward curve's shape (contango/backwardation) carries directional
information. This module extracts, **with no I/O**, three point-in-time descriptors:

- **slope**: linear regression price ~ maturity (``np.polyfit`` degree 1);
- **curvature**: butterfly ``F_short − 2·F_mid + F_long`` (curve convexity);
- **shape**: contango / backwardation / flat according to a named ``flat_tol`` threshold.

Warning: real/simulated boundary (rule ``forward-real-simulated``): the
:class:`TermStructure` result carries a **required** ``simulated`` field (no default). The
compute forward being simulated (CME futures not listed), a result without explicit
labeling is forbidden — the guarantee is enforced by the type.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Literal

import numpy as np

Shape = Literal["contango", "backwardation", "flat"]

#: Default flatness threshold on the slope ($/GPU·h per day) below which shape is classified 'flat'.
DEFAULT_FLAT_TOL = 1e-5


@dataclass(frozen=True)
class TermStructure:
    """Forward curve descriptors at a given instant. ``simulated`` is REQUIRED.

    ``slope`` in $/GPU·h per day, ``curvature`` in $/GPU·h (butterfly). ``shape``
    summarizes the form. ``as_of`` timestamps the fix (point-in-time).
    """

    front_price: float
    slope: float
    curvature: float
    shape: Shape
    as_of: dt.datetime
    simulated: bool


@dataclass(frozen=True)
class TermStructureAnalyzer:
    """Pure forward curve analyzer (Strategy, injectable threshold parameter)."""

    flat_tol: float = DEFAULT_FLAT_TOL

    def analyze(
        self,
        maturities: np.ndarray,
        prices: np.ndarray,
        *,
        simulated: bool,
        as_of: dt.datetime,
    ) -> TermStructure:
        """Computes slope, curvature and shape of the ``(maturities, prices)`` curve.

        Parameters
        ----------
        maturities
            Maturities (days), increasing, length >= 3.
        prices
            Forward prices aligned with ``maturities`` ($/GPU·h).
        simulated
            Real/simulated flag propagated into the result (required).
        as_of
            Fix instant (UTC), timestamped in the result.

        Returns
        -------
        TermStructure
            Descriptors + ``simulated`` flag.
        """
        m = np.asarray(maturities, dtype=float)
        p = np.asarray(prices, dtype=float)
        if m.ndim != 1 or m.size < 3 or m.shape != p.shape:
            raise ValueError("maturities/prices must be 1D and aligned, length >= 3.")

        slope = float(np.polyfit(m, p, 1)[0])
        # Butterfly on (first, median, last) point of the curve: convexity.
        mid = p.size // 2
        curvature = float(p[0] - 2.0 * p[mid] + p[-1])

        if slope > self.flat_tol:
            shape: Shape = "contango"
        elif slope < -self.flat_tol:
            shape = "backwardation"
        else:
            shape = "flat"

        return TermStructure(
            front_price=float(p[0]),
            slope=slope,
            curvature=curvature,
            shape=shape,
            as_of=as_of,
            simulated=simulated,
        )
