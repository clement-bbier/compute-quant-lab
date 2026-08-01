"""Spread mean reversion signal: z-score with a hysteresis band (promoted from P02).

*PoC to foundation* promotion of ``projects/02_spread_mean_reversion``: the canonical logic
(z-score over a point-in-time rolling window + hysteresis entry/exit) moves up here as a
reusable producer. It assumes a validated cointegrated relationship (skill
``/cointegration-analysis``).

Anti look-ahead: only data ``<= t`` (through the P08 ``GuardedView``) feeds the signal at
``t``. Determinism: the hysteresis state is reset at ``view.t == 0`` (two passes over the same
series coincide).
"""

from __future__ import annotations

from core.backtest.protocols import PointInTimeView
from core.signals.protocols import SignalProvenance

#: Minimum number of observations required to define a rolling standard deviation.
_MIN_LOOKBACK: int = 2


class MeanReversionSignal:
    """Hysteresis band on the spread z-score (implements ``SignalProducer``).

    Parameters
    ----------
    z_entry : float
        Entry threshold: a position is taken when ``|z| >= z_entry``.
    z_exit : float
        Exit threshold: the position goes back to flat when ``|z| <= z_exit``. Must be
        ``< z_entry`` (the dead band ``[z_exit, z_entry]`` avoids chattering around a single
        threshold).
    lookback : int
        Rolling window used to estimate the mean/standard deviation of the spread (``>= 2``).
    name : str
        Signal identifier (MLflow tracking / desk attribution).
    simulated : bool
        **Mandatory** real/simulated flag (rule ``forward-real-simulated``).

    Raises
    ------
    ValueError
        If ``z_exit >= z_entry`` or ``lookback < 2``.
    """

    def __init__(
        self,
        *,
        z_entry: float,
        z_exit: float,
        lookback: int,
        name: str = "mean_reversion",
        simulated: bool,
    ) -> None:
        if not z_exit < z_entry:
            raise ValueError(f"z_exit ({z_exit}) must be < z_entry ({z_entry}): empty dead band.")
        if lookback < _MIN_LOOKBACK:
            raise ValueError(f"lookback ({lookback}) must be >= {_MIN_LOOKBACK}.")
        self.z_entry = z_entry
        self.z_exit = z_exit
        self.lookback = lookback
        self.name = name
        self.provenance = SignalProvenance(name=name, simulated=simulated)
        self._position = 0.0

    def decide(self, *, z: float, current_position: float) -> float:
        """Hysteresis band transition: ``(z, current position)`` to target position.

        When flat, the position is taken **against** the deviation (``z >= z_entry`` gives a
        short ``-1``; ``z <= -z_entry`` gives a long ``+1``). When in a position, it is **held**
        while ``|z| > z_exit`` and then **goes back to flat** (never a direct flip ``-1`` to
        ``+1``: a rolling z-score crosses the exit zone before reaching the opposite entry
        band).
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
        """Target position at ``t``: spread z-score over the window ``<= t``, then hysteresis.

        Resets the state at ``view.t == 0`` (reproducibility). Insufficient history or a zero
        standard deviation keeps the current position (nothing new to say, point-in-time).
        """
        if view.t == 0:
            self._position = 0.0
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


__all__ = ["MeanReversionSignal"]
