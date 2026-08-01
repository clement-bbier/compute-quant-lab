"""Portfolio construction: signals → weights → net position (risk-budgeted weighting).

Design decision (PoC): **inverse-vol** ``w_i = (b_i/σ_i) / Σ_j(b_j/σ_j)``, behind a
``WeightScheme`` abstraction that opens the door to **risk-parity / ERC** at the institutional tier
without touching the rest (OCP). ``b_i`` = risk budget (uniform by default).

``PortfolioConstructor`` is **pure**: it takes volatilities already estimated point-in-time
(by ``DeskStrategy``) and the current signals, applies a **vol floor** (anti-domination
by a near-zero-vol signal) then **gross leverage clipping** (``gross_cap``, desk limit).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np

from core.backtest.protocols import FloatArray


def inverse_vol_weights(vols: FloatArray, risk_budget: FloatArray | None = None) -> FloatArray:
    """Normalized inverse-volatility weights (validated design decision).

    ``w_i = (b_i / σ_i) / Σ_j (b_j / σ_j)`` — a less volatile signal gets more weight;
    the risk budget ``b_i`` (uniform if ``None``) modulates the allocation. Weights sum to 1.

    Parameters
    ----------
    vols : FloatArray
        Strictly positive volatilities per signal (already floored by the caller).
    risk_budget : FloatArray, optional
        Relative risk budget per signal; uniform (all equal) by default.

    Returns
    -------
    FloatArray
        Normalized weights, same length as ``vols``, summing to 1.
    """
    budget = (
        np.ones_like(vols) if risk_budget is None else np.asarray(risk_budget, dtype=np.float64)
    )
    raw = budget / vols
    return raw / raw.sum()


@runtime_checkable
class WeightScheme(Protocol):
    """Allocation strategy: volatilities (+ budget) → weights. Extension seam (OCP)."""

    def weights(self, vols: FloatArray, risk_budget: FloatArray | None = None) -> FloatArray: ...


class InverseVolScheme:
    """Inverse-vol allocation (PoC). Delegates to :func:`inverse_vol_weights`."""

    def weights(self, vols: FloatArray, risk_budget: FloatArray | None = None) -> FloatArray:
        return inverse_vol_weights(vols, risk_budget)


class ERCScheme:
    """Equal Risk Contribution (correlation-aware risk-parity) — institutional-tier seam.

    Not implemented at the PoC stage: requires a point-in-time covariance and an iterative
    optimization (§3 institutional). Present to materialize the extension point without
    coding it prematurely.
    """

    def weights(self, vols: FloatArray, risk_budget: FloatArray | None = None) -> FloatArray:
        raise NotImplementedError(
            "ERCScheme (risk-parity) belongs to the institutional tier: see CONVERGENCE.md."
        )


class PortfolioConstructor:
    """Combines estimated volatilities + current signals into a net desk position.

    Parameters
    ----------
    scheme : WeightScheme, optional
        Allocation scheme; ``InverseVolScheme`` by default.
    vol_floor : float
        Floor applied to volatilities before weighting (anti-domination, anti div/0).
    gross_cap : float
        Gross exposure bound |net position| ≤ ``gross_cap`` (desk limit).
    """

    def __init__(
        self,
        scheme: WeightScheme | None = None,
        *,
        vol_floor: float,
        gross_cap: float,
    ) -> None:
        if vol_floor <= 0.0:
            raise ValueError(f"vol_floor ({vol_floor}) must be > 0 (avoids division by zero).")
        if gross_cap <= 0.0:
            raise ValueError(f"gross_cap ({gross_cap}) must be > 0.")
        self.scheme: WeightScheme = scheme or InverseVolScheme()
        self.vol_floor = vol_floor
        self.gross_cap = gross_cap

    def weights(self, vols: FloatArray, risk_budget: FloatArray | None = None) -> FloatArray:
        """Scheme weights after the vol floor (``σ_i ← max(σ_i, vol_floor)``)."""
        floored = np.maximum(np.asarray(vols, dtype=np.float64), self.vol_floor)
        return self.scheme.weights(floored, risk_budget)

    def net_position(self, weights: FloatArray, signals: FloatArray) -> float:
        """Net position = ``clip(Σ w_i·s_i, ±gross_cap)`` (clipped linear combination)."""
        raw = float(np.dot(weights, signals))
        return max(-self.gross_cap, min(self.gross_cap, raw))
