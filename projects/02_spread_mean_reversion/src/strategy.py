"""Mean-reversion strategy on the spread (z-score with a hysteresis band).

Assumes a validated cointegrated relationship (``cointegration.py`` / skill ``/cointegration-analysis``).
The spread is normalized into a z-score over a **point-in-time** rolling window, then we enter
against the deviation when ``|z|`` crosses ``z_entry`` and flatten when ``|z|`` falls back
below ``z_exit`` (the dead band between the two prevents whipsawing). Implements the ``Strategy``
Protocol from ``core.backtest`` (P08): only data ≤ t enters the signal at t.
"""

from __future__ import annotations

from core.backtest import PointInTimeView


class MeanReversionStrategy:
    """Hysteresis band on the spread's z-score (implements P08's ``Strategy`` Protocol).

    Parameters
    ----------
    z_entry : float
        Entry threshold: a position is taken when ``|z| >= z_entry``.
    z_exit : float
        Exit threshold: flattens when ``|z| <= z_exit``. Must be ``< z_entry``
        (the dead band ``[z_exit, z_entry]`` prevents whipsawing around a single threshold).
    lookback : int
        Size of the rolling window used to estimate the spread's mean/std dev (>= 2).

    Raises
    ------
    ValueError
        If ``z_exit >= z_entry`` or ``lookback < 2``.
    """

    def __init__(self, *, z_entry: float, z_exit: float, lookback: int) -> None:
        if not z_exit < z_entry:
            raise ValueError(f"z_exit ({z_exit}) must be < z_entry ({z_entry}): empty dead band.")
        if lookback < 2:
            raise ValueError(f"lookback ({lookback}) must be >= 2 (std dev undefined otherwise).")
        self.z_entry = z_entry
        self.z_exit = z_exit
        self.lookback = lookback
        self._position = 0.0

    def decide(self, *, z: float, current_position: float) -> float:
        """Hysteresis-band transition rule: (z, current position) -> target position.

        Default design choices (adjustable):
        - when flat, enter **against** the deviation: ``z >= z_entry`` -> short (-1), ``z <= -z_entry`` -> long (+1);
        - when in position, **hold** while ``|z| > z_exit``, then **flatten** (never a direct
          flip -1<->+1: a rolling z-score necessarily crosses the exit zone before
          reaching the opposite entry band).
        """
        if current_position == 0.0:
            if z >= self.z_entry:
                return -1.0
            if z <= -self.z_entry:
                return 1.0
            return 0.0
        if abs(z) <= self.z_exit:
            return 0.0
        return current_position

    def signal(self, view: PointInTimeView) -> float:
        """Target position at t: spread z-score on the window ``≤ t`` -> hysteresis rule.

        State is reset when ``view.t == 0`` so that two runs on the same series are
        identical (determinism). Insufficient history or zero std dev -> the position is kept as is.
        """
        if view.t == 0:
            self._position = 0.0  # start of a run: reset to flat (reproducibility)
        history = view.history()
        if history.size < self.lookback:
            return self._position
        recent = history[-self.lookback :]
        std = float(recent.std(ddof=1))
        if std == 0.0:
            return self._position
        z = (view.latest() - float(recent.mean())) / std
        self._position = self.decide(z=z, current_position=self._position)
        return self._position
