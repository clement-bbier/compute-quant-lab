"""Two-phase backtest engine (point-in-time, reproducible).

Phase 1 (Python, *guarded*): at each t the strategy receives a ``GuardedView`` of
data up to t and returns a position. The look-ahead guard lives here: a strategy
that reads the future fails the run.

Phase 2 (accumulation): Rust is the **fast path**, the Python oracle is the
**fallback**. ``backtest_loop.accumulate`` walks the long history and accumulates
PnL; when the crate is not compiled, the engine falls back to
:func:`core.backtest.reference_loop.accumulate`, which is the reference
specification the kernel is tested against for bit-for-bit parity
(``test_parity``). Results are therefore identical either way -- only speed
differs -- so ``import core.backtest`` never requires ``maturin develop``.

This mirrors the optional-kernel policy of P01 (:class:`core.pricing.pricer`),
where the Rust spread kernel is likewise additive rather than mandatory.
See ``core/backtest/_loop/README.md`` for the build instructions.
"""

from __future__ import annotations

from typing import Any, Protocol

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
from core.utils.logging import get_logger

logger = get_logger(__name__)


class _Accumulator(Protocol):
    """Phase-2 kernel signature, shared by the Rust fast path and the Python oracle."""

    def __call__(
        self,
        positions: FloatArray,
        prices: FloatArray,
        fees_bps: float,
        slippage_bps: float,
    ) -> tuple[FloatArray, int]: ...


try:  # Rust fast path -- additive, never required.
    from backtest_loop import accumulate as _accumulate

    USING_RUST_KERNEL = True
except ImportError:  # pragma: no cover - depends on whether the crate is built
    from core.backtest.reference_loop import accumulate as _accumulate

    USING_RUST_KERNEL = False
    logger.warning(
        "Rust kernel 'backtest_loop' unavailable: falling back to the Python oracle "
        "(slow path, bit-for-bit identical results). Run 'maturin develop -m "
        "core/backtest/_loop/Cargo.toml' for the fast path."
    )

#: Phase-2 accumulation kernel actually in use (Rust fast path, or Python oracle).
accumulate: _Accumulator = _accumulate

#: Reference capital of the PoC (PnL expressed in units of initial capital).
DEFAULT_CAPITAL: float = 1.0


class BacktestEngine:
    """Orchestrate both phases through injected abstractions (SOLID / DI).

    The injected ``LinearCostModel`` feeds the accumulation loop (linear costs in
    bps); non-linear cost models belong to the institutional tier (Python phase 2).
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
        """Run the backtest and return a pure ``BacktestResult`` (no I/O)."""
        positions = self._generate_positions(prices, strategy)  # phase 1 (guarded)
        returns, n_trades = accumulate(  # phase 2 (Rust fast path, or Python oracle)
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
        """Phase 1: sequential position generation under the look-ahead guard."""
        n = prices.shape[0]
        positions = np.empty(n, dtype=np.float64)
        for t in range(n):
            positions[t] = strategy.signal(GuardedView(prices, t))
        return positions
