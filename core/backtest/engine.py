"""Moteur de backtest deux phases (point-in-time, reproductible).

Phase 1 (Python, *guardée*) : à chaque t, une `GuardedView` ≤ t est passée à la
stratégie → tableau de positions. Le garde-fou look-ahead vit ici : une stratégie
qui lit le futur fait échouer le run.

Phase 2 (Rust, *obligatoire*) : `backtest_loop.accumulate` parcourt l'historique
long et accumule le PnL. L'import est **dur** : sans le crate compilé, le moteur
ne s'importe pas (cf. `core/backtest/_loop/README.md`). L'oracle Python équivalent
(`reference_loop`) ne sert qu'aux tests de parité.
"""

from __future__ import annotations

from typing import Any

import backtest_loop  # noyau Rust OBLIGATOIRE — aucun fallback runtime
import numpy as np

from core.backtest.costs import LinearCostModel
from core.backtest.guards import GuardedView
from core.backtest.metrics import DefaultMetrics
from core.backtest.protocols import (
    BacktestResult,
    FloatArray,
    Ledger,
    MetricsCalculator,
    Strategy,
)

#: Capital de référence du PoC (PnL exprimé en unités de capital initial).
DEFAULT_CAPITAL: float = 1.0


class BacktestEngine:
    """Orchestre les deux phases via des abstractions injectées (SOLID / DI).

    Le `LinearCostModel` injecté alimente la boucle Rust (coûts linéaires en bps) ;
    des modèles de coût non linéaires relèvent du palier institutionnel (phase 2 Python).
    """

    def __init__(
        self,
        *,
        cost_model: LinearCostModel,
        periods_per_year: float,
        capital: float = DEFAULT_CAPITAL,
        risk_free_rate: float = 0.0,
        metrics: MetricsCalculator | None = None,
    ) -> None:
        self.cost_model = cost_model
        self.capital = capital
        self.metrics: MetricsCalculator = metrics or DefaultMetrics(
            periods_per_year, risk_free_rate
        )

    def run(
        self,
        prices: FloatArray,
        strategy: Strategy,
        params: dict[str, Any] | None = None,
    ) -> BacktestResult:
        """Exécute le backtest et renvoie un `BacktestResult` pur (sans I/O)."""
        positions = self._generate_positions(prices, strategy)  # phase 1 (guardée)
        returns, n_trades = backtest_loop.accumulate(  # phase 2 (Rust)
            positions, prices, self.cost_model.fees_bps, self.cost_model.slippage_bps
        )
        pnl = returns * self.capital
        equity_curve = self.capital + np.cumsum(pnl)
        ledger = Ledger(
            returns=returns,
            pnl=pnl,
            equity_curve=equity_curve,
            positions=positions,
            n_trades=n_trades,
        )
        return BacktestResult(
            ledger=ledger,
            metrics=self.metrics.compute(ledger),
            params=params or {},
        )

    @staticmethod
    def _generate_positions(prices: FloatArray, strategy: Strategy) -> FloatArray:
        """Phase 1 : génération séquentielle des positions sous garde-fou anti look-ahead."""
        n = prices.shape[0]
        positions = np.empty(n, dtype=np.float64)
        for t in range(n):
            positions[t] = strategy.signal(GuardedView(prices, t))
        return positions
