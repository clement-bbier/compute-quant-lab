"""Shared numeric array aliases used across the library's protocol modules.

Single definition point for the NumPy array aliases that the ``backtest``,
``pricing``, ``features`` and ``models`` protocol modules all need. Each of those
modules re-imports and re-exports the aliases, so their public names stay
unchanged while the definition lives here.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

#: Contiguous array of 64-bit floats (prices, returns, spreads, positions).
FloatArray = NDArray[np.float64]

#: Contiguous array of 64-bit signed integers (indices, counts, discrete states).
IntArray = NDArray[np.int64]

__all__ = ["FloatArray", "IntArray"]
