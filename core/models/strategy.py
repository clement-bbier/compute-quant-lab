"""Adapter: precomputed ML signal -> ``Strategy`` of the P08 backtest engine.

The P08 engine only hands the strategy a `PointInTimeView` on the **price series**; it knows
nothing about features. The decoupling therefore happens in two steps: (1) an out-of-sample
probability vector is computed upstream (purged CV, see `validation.oos_predict`), aligned
1:1 with the backtested series; (2) this thin strategy reads the probability at ``view.t``
and maps it to a position. Consequence: the model never "sees" the prices at runtime — any
potential leak was neutralized upstream, and the ``GuardedView`` guardrail stays free.

The probability-to-position rule carries the adapter's single risk trade-off (neutral band).
"""

from __future__ import annotations

import numpy as np

# The `protocols` submodule is targeted (numpy only), not `core.backtest` whose __init__
# imports the engine and its Rust core: the model layer thus stays importable and testable
# without a Rust build (the real backtest composes the engine at the project level).
from core.backtest.protocols import PointInTimeView
from core.models.protocols import FloatArray

#: Indifference probability: 0.5 = the model has no directional view.
_INDIFFERENCE = 0.5


class PrecomputedSignalStrategy:
    """Map a precomputed OOS probability to a position (implements the P08 `Strategy`).

    Parameters
    ----------
    proba
        ``P(up)`` vector aligned on the backtested series. ``NaN`` (no prediction available:
        warm-up / non-observable tail) implies a flat position.
    neutral_band
        Half-width of the dead band around 0.5. ``0`` = a side is always taken; wider = stay
        flat as long as the model is uncertain (lower turnover/costs, lower exposure). Must
        be in ``[0, 0.5)``.

    Raises
    ------
    ValueError
        If ``neutral_band`` is not in ``[0, 0.5)``.
    """

    def __init__(self, proba: FloatArray, *, neutral_band: float = 0.0) -> None:
        if not 0.0 <= neutral_band < 0.5:
            raise ValueError(f"neutral_band ({neutral_band}) must be in [0, 0.5).")
        self._proba = np.asarray(proba, dtype=np.float64)
        self._neutral_band = neutral_band

    def _to_position(self, p: float) -> float:
        """Probability-to-position rule: long above the band, short below, flat inside."""
        if p > _INDIFFERENCE + self._neutral_band:
            return 1.0
        if p < _INDIFFERENCE - self._neutral_band:
            return -1.0
        return 0.0

    def signal(self, view: PointInTimeView) -> float:
        """Target position at ``view.t``: maps that instant's OOS probability (NaN = flat)."""
        p = float(self._proba[view.t])
        if np.isnan(p):
            return 0.0
        return self._to_position(p)


__all__ = ["PrecomputedSignalStrategy"]
