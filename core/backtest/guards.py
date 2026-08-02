"""Anti look-ahead guard.

`GuardedView` wraps a series and only exposes values ≤ t. Any access to the
future raises `LookAheadError`: this is the mechanism that makes look-ahead bias
**impossible to ignore** — a signal that cheats makes the run fail.

Deliberate parallel with `core.features.builders.assert_point_in_time`: over there a
feature-building-time guardrail; here the same intransigence at backtest runtime. Both
log the violation at ERROR before raising (observability rule: a look-ahead raise is a
failed operation, not a recoverable fallback), independently -- the two modules stay
decoupled (no cross-import).
"""

from __future__ import annotations

from core.backtest.protocols import FloatArray
from core.utils.logging import get_logger

logger = get_logger(__name__)


class LookAheadError(RuntimeError):
    """Raised when a signal tries to read data later than instant t."""


class GuardedView:
    """Point-in-time view on a series: sees only ≤ t (implements PointInTimeView)."""

    def __init__(self, data: FloatArray, t: int) -> None:
        if not 0 <= t < data.shape[0]:
            raise IndexError(f"t ({t}) must be within a series of length {data.shape[0]}.")
        self._data = data
        self.t = t

    def history(self) -> FloatArray:
        """Copy of the values known up to and including t (no aliasing with engine data)."""
        return self._data[: self.t + 1].copy()

    def latest(self) -> float:
        """Value at the current instant t."""
        return float(self._data[self.t])

    def at(self, i: int) -> float:
        """Value at index i. Raises `LookAheadError` if i > t, `IndexError` if i < 0.

        Negative indices are refused: `at(-1)` would wrap around in numpy to the end
        of the series (hence the future), which would be a disguised look-ahead.
        """
        if i < 0:
            raise IndexError(f"i ({i}) must be non-negative (wrap-around forbidden).")
        if i > self.t:
            message = f"i ({i}) must not exceed t ({self.t}): future access forbidden."
            logger.error(message)
            raise LookAheadError(message)
        return float(self._data[i])
