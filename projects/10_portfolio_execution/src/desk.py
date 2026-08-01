"""Composite desk strategy: blends N signals into ONE net position (injected into P08).

The P08 engine is single-series: ``signal(view) -> float``. ``DeskStrategy`` is therefore a
composite ``Strategy`` that, at each t:
1. queries each producer (mock at the PoC stage) via the ``GuardedView`` ≤ t → directional view ``s_i,t``;
2. estimates, **point-in-time**, the realized volatility of each signal over a window ≤ t
   (lagged realized return ``s_i,{t-1}·market_return[t]``);
3. derives weights from that (``PortfolioConstructor``) and returns the clipped net position ``Σ w_i·s_i``.

Anti look-ahead: everything feeding the decision at t comes from the ``GuardedView`` (≤ t); the
vol uses realized returns whose most recent value only depends on ``price[t]`` (observed at t).
Determinism: state is reset at ``t == 0`` (two runs on the same series match exactly).

For "contribution by signal" attribution, the desk records at each step the
**component positions** ``c_i = w_i·s_i`` (re-normalized after clipping so that ``Σ_i c_i``
exactly equals the net position).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from core.backtest.protocols import FloatArray, PointInTimeView

from portfolio import PortfolioConstructor
from signals import SignalProducer

#: Minimum number of realized returns before estimating a vol (equal-weighted otherwise).
_MIN_VOL_OBS: int = 2


@dataclass(frozen=True)
class DeskHistory:
    """Per-timestep desk history (for attribution and reproducibility).

    All matrices have shape ``(n_steps, n_signals)``; ``positions``/``mkt_returns``
    have length ``n_steps``.
    """

    mkt_returns: FloatArray
    signals: FloatArray
    weights: FloatArray
    components: FloatArray
    positions: FloatArray


class DeskStrategy:
    """Combines signal producers into a net position (implements P08's ``Strategy``).

    Parameters
    ----------
    producers : list[SignalProducer]
        Injected signal producers (mocks at the PoC stage; P02/P06/P09 at convergence).
    constructor : PortfolioConstructor
        Weighting policy + vol floor + leverage clipping.
    vol_lookback : int
        Estimation window for per-signal realized volatility (≥ 2).
    """

    def __init__(
        self,
        producers: list[SignalProducer],
        constructor: PortfolioConstructor,
        *,
        vol_lookback: int,
    ) -> None:
        if not producers:
            raise ValueError("at least one signal producer is required.")
        if vol_lookback < _MIN_VOL_OBS:
            raise ValueError(f"vol_lookback ({vol_lookback}) must be ≥ {_MIN_VOL_OBS}.")
        self.producers = producers
        self.constructor = constructor
        self.vol_lookback = vol_lookback
        self._reset()

    # -- sequential state (reset at t == 0) ------------------------------------------------

    def _reset(self) -> None:
        k = len(self.producers)
        self._prev_signals = np.zeros(k, dtype=np.float64)
        self._returns_buffer: list[FloatArray] = []  # realized returns per signal, per step
        self._rec_mkt: list[float] = []
        self._rec_signals: list[FloatArray] = []
        self._rec_weights: list[FloatArray] = []
        self._rec_components: list[FloatArray] = []
        self._rec_positions: list[float] = []

    def _estimate_vols(self) -> FloatArray:
        """Realized vol per signal over the ``vol_lookback`` window (equal-weighted during warmup)."""
        k = len(self.producers)
        if len(self._returns_buffer) < _MIN_VOL_OBS:
            return np.ones(k, dtype=np.float64)
        window = np.array(self._returns_buffer[-self.vol_lookback :])  # (m, k)
        return window.std(axis=0, ddof=1)

    # -- P08 Strategy contract --------------------------------------------------------------

    def signal(self, view: PointInTimeView) -> float:
        """Net position at t, decided on data ≤ t (point-in-time, deterministic)."""
        t = view.t
        if t == 0:
            self._reset()
            mkt_ret = 0.0
        else:
            mkt_ret = view.latest() / view.at(t - 1) - 1.0
            # realized return over [t-1, t] of each signal = held position (s_{t-1}) · market.
            self._returns_buffer.append(self._prev_signals * mkt_ret)

        current = np.array([p.signal(view) for p in self.producers], dtype=np.float64)
        weights = self.constructor.weights(self._estimate_vols())
        position = self.constructor.net_position(weights, current)

        # Components re-normalized after clipping: Σ_i c_i == net position (exact attribution).
        raw = float(np.dot(weights, current))
        scale = position / raw if raw != 0.0 else 0.0
        components = weights * current * scale

        self._record(mkt_ret, current, weights, components, position)
        self._prev_signals = current
        return position

    def _record(
        self,
        mkt_ret: float,
        signals: FloatArray,
        weights: FloatArray,
        components: FloatArray,
        position: float,
    ) -> None:
        self._rec_mkt.append(mkt_ret)
        self._rec_signals.append(signals)
        self._rec_weights.append(weights)
        self._rec_components.append(components)
        self._rec_positions.append(position)

    def history(self) -> DeskHistory:
        """Accumulated history of the last run (for attribution and MLflow logging)."""
        return DeskHistory(
            mkt_returns=np.array(self._rec_mkt, dtype=np.float64),
            signals=np.array(self._rec_signals, dtype=np.float64),
            weights=np.array(self._rec_weights, dtype=np.float64),
            components=np.array(self._rec_components, dtype=np.float64),
            positions=np.array(self._rec_positions, dtype=np.float64),
        )
