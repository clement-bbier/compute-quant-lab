"""Adaptateur signal ML → ``Strategy`` du moteur P08.

Le modèle ne *voit* pas les prix au runtime : la stratégie ne fait que lire la
probabilité OOS pré-calculée à ``view.t`` et la mappe en position. Tout le risque de
fuite a été neutralisé en amont (purged-CV). Ici on teste l'adaptateur, pas le modèle.
"""

from __future__ import annotations

import numpy as np

# Sous-modules sans dépendance Rust (cf. core.models.strategy) : la suite reste
# exécutable sans avoir compilé le noyau `backtest_loop`.
from core.backtest.guards import GuardedView
from core.backtest.protocols import Strategy
from core.models.strategy import PrecomputedSignalStrategy


def _view(n: int, t: int) -> GuardedView:
    """Vue point-in-time réelle de P08 sur une série bidon (seul ``.t`` est lu)."""
    return GuardedView(np.zeros(n, dtype=np.float64), t)


def test_conforms_to_strategy_protocol() -> None:
    strat = PrecomputedSignalStrategy(np.full(10, 0.5), neutral_band=0.1)
    assert isinstance(strat, Strategy)


def test_returns_position_for_current_index() -> None:
    proba = np.array([0.9, 0.1, 0.5, 0.8, 0.2])
    strat = PrecomputedSignalStrategy(proba, neutral_band=0.1)
    positions = [strat.signal(_view(proba.size, t)) for t in range(proba.size)]
    assert positions == [1.0, -1.0, 0.0, 1.0, -1.0]


def test_neutral_band_keeps_uncertain_predictions_flat() -> None:
    proba = np.array([0.55, 0.45, 0.66, 0.34])
    strat = PrecomputedSignalStrategy(proba, neutral_band=0.10)
    positions = [strat.signal(_view(proba.size, t)) for t in range(proba.size)]
    # 0.55 et 0.45 sont dans la bande [0.40, 0.60] → plat ; 0.66/0.34 → pris.
    assert positions == [0.0, 0.0, 1.0, -1.0]


def test_only_reads_current_index_never_future() -> None:
    """La position à ``t`` ne dépend pas du futur de la série de probabilités."""
    proba = np.array([0.8, 0.2, 0.9, 0.1, 0.7])
    strat = PrecomputedSignalStrategy(proba.copy(), neutral_band=0.05)
    t = 1
    before = strat.signal(_view(proba.size, t))
    tampered = proba.copy()
    tampered[t + 1 :] = 1.0  # on force tout le futur à « long »
    after = PrecomputedSignalStrategy(tampered, neutral_band=0.05).signal(_view(proba.size, t))
    assert before == after


def test_is_deterministic() -> None:
    proba = np.array([0.7, 0.3, 0.5, 0.6])
    a = [PrecomputedSignalStrategy(proba, neutral_band=0.0).signal(_view(4, t)) for t in range(4)]
    b = [PrecomputedSignalStrategy(proba, neutral_band=0.0).signal(_view(4, t)) for t in range(4)]
    assert a == b
