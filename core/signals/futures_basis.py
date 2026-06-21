"""Signal de base future↔spot : carry/roll point-in-time (sur le cost-of-carry de P06).

À chaque ``t``, on price la **base** ``basis_t = F_t − S_t`` via le pricer cost-of-carry de
``core.pricing.derivatives`` (P06) — ``F = S·e^{(r−y)τ}`` — puis on rend le **z-score de la
variation de base** sur la fenêtre ``<= t`` :

    s_t = clip( (Δbasis_t − μ(Δbasis fenêtre)) / σ(Δbasis fenêtre),  −1, 1 )

Économie (option A, *carry momentum*) : on **suit l'élargissement** de la base (signal long quand
la base s'élargit anormalement vite). Saveur momentum, **distincte** du retour à la moyenne de P02
(qui z-score le *niveau* du prix) → les deux signaux ne sont pas colinéaires dans l'agrégation desk.

Frontière réel/simulé : les futures compute (settlement SDH100RT) ne sont **pas listés** ; toute
forward produite par P06 est simulée → ``provenance.simulated`` est dérivé du modèle de portage
(toujours ``True``), jamais oublié (rule ``forward-real-simulated``).

Anti look-ahead : seules des données ``<= t`` (``GuardedView`` de P08) entrent dans le signal à ``t``.
"""

from __future__ import annotations

import numpy as np

from core.backtest.protocols import PointInTimeView
from core.pricing.derivatives.carry import DEFAULT_RISK_FREE_RATE, CostOfCarryModel
from core.pricing.derivatives.futures import CarryFuturesPricer
from core.pricing.derivatives.protocols import CarryModel
from core.signals.protocols import SignalProvenance, clip_unit

#: Nombre minimal de variations de base pour estimer un écart-type glissant.
_MIN_LOOKBACK: int = 2


class FuturesBasisSignal:
    """Carry/roll momentum sur la base future↔spot (implémente ``SignalProducer``).

    Parameters
    ----------
    tau_years : float
        Maturité ``τ`` (années) du future théorique servant à calculer la base (``> 0``).
    lookback : int
        Fenêtre glissante de variations de base pour le z-score (``>= 2``).
    carry_model : CarryModel, optional
        Source de forward ; ``CostOfCarryModel()`` (cost-of-carry P06) par défaut.
    rate : float
        Taux de financement annualisé transmis au pricer P06 (yield implicite, sensibilités).
    name : str
        Identifiant du signal (tracé MLflow / attribution desk).

    Raises
    ------
    ValueError
        Si ``tau_years <= 0`` ou ``lookback < 2``.
    """

    def __init__(
        self,
        *,
        tau_years: float,
        lookback: int,
        carry_model: CarryModel | None = None,
        rate: float = DEFAULT_RISK_FREE_RATE,
        name: str = "futures_basis",
    ) -> None:
        if tau_years <= 0.0:
            raise ValueError(f"tau_years ({tau_years}) doit être > 0.")
        if lookback < _MIN_LOOKBACK:
            raise ValueError(f"lookback ({lookback}) doit être >= {_MIN_LOOKBACK}.")
        model: CarryModel = carry_model if carry_model is not None else CostOfCarryModel()
        self._pricer = CarryFuturesPricer(model, rate)
        self._tau = tau_years
        self.lookback = lookback
        self.name = name
        # Forward compute non listé ⇒ simulée ; on dérive le drapeau du modèle (jamais oublié).
        self.provenance = SignalProvenance(name=name, simulated=model.simulated)

    def _basis(self, spot: float) -> float:
        """Base théorique ``F − S`` à ce spot, via le pricer cost-of-carry de P06."""
        return self._pricer.price(spot, self._tau).basis

    def signal(self, view: PointInTimeView) -> float:
        """Position cible à ``t`` : z-score de la variation de base sur la fenêtre ``<= t``.

        Il faut ``lookback + 1`` prix (donc ``lookback`` variations) ; en deçà, ou si la variation
        de base est d'écart-type nul (prix constants), on reste plat (0) — rien de neuf à dire.
        """
        history = view.history()
        if history.size < self.lookback + 1:
            return 0.0
        window_prices = history[-(self.lookback + 1) :]
        basis = np.array([self._basis(float(p)) for p in window_prices], dtype=np.float64)
        delta = np.diff(basis)  # longueur = lookback
        std = float(delta.std(ddof=1))
        if std == 0.0:
            return 0.0
        z = (float(delta[-1]) - float(delta.mean())) / std
        return clip_unit(z)


__all__ = ["FuturesBasisSignal"]
