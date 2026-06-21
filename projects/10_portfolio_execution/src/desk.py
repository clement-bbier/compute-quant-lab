"""Stratégie composite du desk : fond N signaux en UNE position nette (injectée dans P08).

Le moteur P08 est mono-série : ``signal(view) -> float``. Le ``DeskStrategy`` est donc une
``Strategy`` composite qui, à chaque t :
1. interroge chaque producteur (mock au PoC) via la ``GuardedView`` ≤ t → vue directionnelle ``s_i,t`` ;
2. estime, **point-in-time**, la volatilité réalisée de chaque signal sur une fenêtre ≤ t
   (rendement réalisé laggé ``s_i,{t-1}·rendement_marché[t]``) ;
3. en déduit des poids (``PortfolioConstructor``) et renvoie la position nette ``Σ w_i·s_i`` écrêtée.

Anti look-ahead : tout ce qui entre dans la décision à t vient de la ``GuardedView`` (≤ t) ; la
vol utilise des rendements réalisés dont le plus récent ne dépend que de ``prix[t]`` (observé à t).
Déterminisme : l'état est réinitialisé à ``t == 0`` (deux runs sur la même série coïncident).

Pour l'attribution « contribution par signal », le desk mémorise à chaque pas les
**positions-composantes** ``c_i = w_i·s_i`` (re-normalisées après écrêtage pour que ``Σ_i c_i``
égale exactement la position nette).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from core.backtest.protocols import FloatArray, PointInTimeView

from portfolio import PortfolioConstructor
from signals import SignalProducer

#: Nombre minimal de rendements réalisés avant d'estimer une vol (sinon équipondération).
_MIN_VOL_OBS: int = 2


@dataclass(frozen=True)
class DeskHistory:
    """Historique par pas de temps du desk (pour l'attribution et la reproductibilité).

    Toutes les matrices ont la forme ``(n_pas, n_signaux)`` ; ``positions``/``mkt_returns``
    sont de longueur ``n_pas``.
    """

    mkt_returns: FloatArray
    signals: FloatArray
    weights: FloatArray
    components: FloatArray
    positions: FloatArray


class DeskStrategy:
    """Combine des producteurs de signaux en une position nette (implémente ``Strategy`` de P08).

    Parameters
    ----------
    producers : list[SignalProducer]
        Producteurs de signaux injectés (mocks au PoC ; P02/P06/P09 en convergence).
    constructor : PortfolioConstructor
        Politique de pondération + plancher de vol + écrêtage de levier.
    vol_lookback : int
        Fenêtre d'estimation de la volatilité réalisée par signal (≥ 2).
    """

    def __init__(
        self,
        producers: list[SignalProducer],
        constructor: PortfolioConstructor,
        *,
        vol_lookback: int,
    ) -> None:
        if not producers:
            raise ValueError("au moins un producteur de signaux est requis.")
        if vol_lookback < _MIN_VOL_OBS:
            raise ValueError(f"vol_lookback ({vol_lookback}) doit être ≥ {_MIN_VOL_OBS}.")
        self.producers = producers
        self.constructor = constructor
        self.vol_lookback = vol_lookback
        self._reset()

    # -- état séquentiel (reset à t == 0) --------------------------------------------------

    def _reset(self) -> None:
        k = len(self.producers)
        self._prev_signals = np.zeros(k, dtype=np.float64)
        self._returns_buffer: list[FloatArray] = []  # rendements réalisés par signal, par pas
        self._rec_mkt: list[float] = []
        self._rec_signals: list[FloatArray] = []
        self._rec_weights: list[FloatArray] = []
        self._rec_components: list[FloatArray] = []
        self._rec_positions: list[float] = []

    def _estimate_vols(self) -> FloatArray:
        """Vol réalisée par signal sur la fenêtre ``vol_lookback`` (équipondération en warmup)."""
        k = len(self.producers)
        if len(self._returns_buffer) < _MIN_VOL_OBS:
            return np.ones(k, dtype=np.float64)
        window = np.array(self._returns_buffer[-self.vol_lookback :])  # (m, k)
        return window.std(axis=0, ddof=1)

    # -- contrat Strategy de P08 -----------------------------------------------------------

    def signal(self, view: PointInTimeView) -> float:
        """Position nette à t, décidée sur des données ≤ t (point-in-time, déterministe)."""
        t = view.t
        if t == 0:
            self._reset()
            mkt_ret = 0.0
        else:
            mkt_ret = view.latest() / view.at(t - 1) - 1.0
            # rendement réalisé sur [t-1, t] de chaque signal = position tenue (s_{t-1}) · marché.
            self._returns_buffer.append(self._prev_signals * mkt_ret)

        current = np.array([p.signal(view) for p in self.producers], dtype=np.float64)
        weights = self.constructor.weights(self._estimate_vols())
        position = self.constructor.net_position(weights, current)

        # Composantes re-normalisées après écrêtage : Σ_i c_i == position nette (attribution exacte).
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
        """Historique accumulé du dernier run (pour attribution et logging MLflow)."""
        return DeskHistory(
            mkt_returns=np.array(self._rec_mkt, dtype=np.float64),
            signals=np.array(self._rec_signals, dtype=np.float64),
            weights=np.array(self._rec_weights, dtype=np.float64),
            components=np.array(self._rec_components, dtype=np.float64),
            positions=np.array(self._rec_positions, dtype=np.float64),
        )
