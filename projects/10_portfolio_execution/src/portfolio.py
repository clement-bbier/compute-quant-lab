"""Construction de portefeuille : signaux → poids → position nette (pondération sous risque).

Décision de design (PoC) : **inverse-vol** ``w_i = (b_i/σ_i) / Σ_j(b_j/σ_j)``, derrière une
abstraction ``WeightScheme`` qui ouvre la porte au **risk-parity / ERC** au palier institutionnel
sans toucher au reste (OCP). ``b_i`` = budget de risque (uniforme par défaut).

Le ``PortfolioConstructor`` est **pur** : il prend des volatilités déjà estimées point-in-time
(par le ``DeskStrategy``) et les signaux courants, applique un **plancher de vol** (anti-domination
d'un signal à vol quasi nulle) puis un **écrêtage de levier brut** (``gross_cap``, limite desk).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np

from core.backtest.protocols import FloatArray


def inverse_vol_weights(vols: FloatArray, risk_budget: FloatArray | None = None) -> FloatArray:
    """Poids inverse-volatilité normalisés (décision de design validée).

    ``w_i = (b_i / σ_i) / Σ_j (b_j / σ_j)`` — un signal moins volatil reçoit plus de poids ;
    le budget de risque ``b_i`` (uniforme si ``None``) module l'allocation. Les poids somment à 1.

    Parameters
    ----------
    vols : FloatArray
        Volatilités strictement positives par signal (déjà planchées par l'appelant).
    risk_budget : FloatArray, optional
        Budget de risque relatif par signal ; uniforme (tous égaux) par défaut.

    Returns
    -------
    FloatArray
        Poids normalisés, de même longueur que ``vols``, de somme 1.
    """
    budget = (
        np.ones_like(vols) if risk_budget is None else np.asarray(risk_budget, dtype=np.float64)
    )
    raw = budget / vols
    return raw / raw.sum()


@runtime_checkable
class WeightScheme(Protocol):
    """Stratégie d'allocation : volatilités (+ budget) → poids. Seam d'extension (OCP)."""

    def weights(self, vols: FloatArray, risk_budget: FloatArray | None = None) -> FloatArray: ...


class InverseVolScheme:
    """Allocation inverse-vol (PoC). Délègue à :func:`inverse_vol_weights`."""

    def weights(self, vols: FloatArray, risk_budget: FloatArray | None = None) -> FloatArray:
        return inverse_vol_weights(vols, risk_budget)


class ERCScheme:
    """Equal Risk Contribution (risk-parity corrélation-aware) — seam du palier institutionnel.

    Non implémenté au PoC : nécessite une covariance point-in-time et une optimisation itérative
    (§3 institutionnel). Présent pour matérialiser le point d'extension sans le coder prématurément.
    """

    def weights(self, vols: FloatArray, risk_budget: FloatArray | None = None) -> FloatArray:
        raise NotImplementedError(
            "ERCScheme (risk-parity) relève du palier institutionnel : voir CONVERGENCE.md."
        )


class PortfolioConstructor:
    """Combine des volatilités estimées + signaux courants en une position nette de desk.

    Parameters
    ----------
    scheme : WeightScheme, optional
        Schéma d'allocation ; ``InverseVolScheme`` par défaut.
    vol_floor : float
        Plancher appliqué aux volatilités avant pondération (anti-domination, anti div/0).
    gross_cap : float
        Borne d'exposition brute |position nette| ≤ ``gross_cap`` (limite desk).
    """

    def __init__(
        self,
        scheme: WeightScheme | None = None,
        *,
        vol_floor: float,
        gross_cap: float,
    ) -> None:
        if vol_floor <= 0.0:
            raise ValueError(f"vol_floor ({vol_floor}) doit être > 0 (évite la division par zéro).")
        if gross_cap <= 0.0:
            raise ValueError(f"gross_cap ({gross_cap}) doit être > 0.")
        self.scheme: WeightScheme = scheme or InverseVolScheme()
        self.vol_floor = vol_floor
        self.gross_cap = gross_cap

    def weights(self, vols: FloatArray, risk_budget: FloatArray | None = None) -> FloatArray:
        """Poids du schéma après plancher de vol (``σ_i ← max(σ_i, vol_floor)``)."""
        floored = np.maximum(np.asarray(vols, dtype=np.float64), self.vol_floor)
        return self.scheme.weights(floored, risk_budget)

    def net_position(self, weights: FloatArray, signals: FloatArray) -> float:
        """Position nette = ``clip(Σ w_i·s_i, ±gross_cap)`` (combinaison linéaire écrêtée)."""
        raw = float(np.dot(weights, signals))
        return max(-self.gross_cap, min(self.gross_cap, raw))
