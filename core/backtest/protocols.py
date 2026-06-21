"""Contrats du moteur de backtest (SOLID / DI).

Le moteur orchestre via ces abstractions : `Strategy`, `CostModel`,
`MetricsCalculator` et `PointInTimeView` sont **injectés**, jamais codés en dur.
Un nouveau type de stratégie ne modifie donc pas le moteur (OCP).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

import numpy as np
from numpy.typing import NDArray

#: Tableau de flottants double précision (les séries du moteur sont en float64).
FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class Trade:
    """Variation de position à un instant donné (ce qui déclenche un coût)."""

    t: int
    delta_position: float
    price: float


@dataclass(frozen=True)
class Ledger:
    """Sortie de la phase 2 : comptabilité période par période.

    Tous les tableaux ont la même longueur que la série de prix.
    """

    returns: FloatArray
    pnl: FloatArray
    equity_curve: FloatArray
    positions: FloatArray
    n_trades: int


@dataclass(frozen=True)
class BacktestResult:
    """Résultat *pur* d'un run : comptabilité + métriques + params.

    Les métadonnées de reproductibilité (SHA git, version DVC, run_id) ne vivent
    pas ici : elles sont loggées dans MLflow par `core.backtest.tracking` (le run
    est rejouable depuis son seul run_id MLflow). Garde le moteur sans I/O caché.
    """

    ledger: Ledger
    metrics: dict[str, float]
    params: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class PointInTimeView(Protocol):
    """Vue de données restreinte à l'instant courant t : ne voit que ≤ t.

    Toute tentative d'accès à un index > t doit lever `LookAheadError`.
    """

    #: Index temporel courant (les stratégies indexent relativement à `t`).
    t: int

    def history(self) -> FloatArray:
        """Toutes les valeurs connues jusqu'à t inclus."""
        ...

    def latest(self) -> float:
        """Valeur à l'instant courant t."""
        ...

    def at(self, i: int) -> float:
        """Valeur à l'index i ; lève `LookAheadError` si i > t."""
        ...


@runtime_checkable
class Strategy(Protocol):
    """Produit une position cible à t à partir de données ≤ t uniquement."""

    def signal(self, view: PointInTimeView) -> float:
        ...


@runtime_checkable
class CostModel(Protocol):
    """Coût (€) d'un trade : frais + slippage."""

    def cost(self, trade: Trade) -> float:
        ...


@runtime_checkable
class MetricsCalculator(Protocol):
    """Calcule les métriques de risque à partir d'un `Ledger`."""

    def compute(self, ledger: Ledger) -> dict[str, float]:
        ...
