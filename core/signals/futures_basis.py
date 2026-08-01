"""Future/spot basis signal: point-in-time carry/roll (on top of the P06 cost-of-carry).

At each ``t``, the **basis** ``basis_t = F_t - S_t`` is priced with the cost-of-carry pricer of
``core.pricing.derivatives`` (P06) — ``F = S·e^{(r-y)tau}`` — and the returned value is the
**z-score of the basis change** over the window ``<= t``:

    s_t = clip( (dbasis_t - mu(dbasis window)) / sigma(dbasis window),  -1, 1 )

Economics (option A, *carry momentum*): the signal **follows the widening** of the basis (long
when the basis widens abnormally fast). A momentum flavour, **distinct** from the P02 mean
reversion (which z-scores the price *level*), so the two signals are not collinear in the desk
aggregation.

Real/simulated boundary: compute futures (settlement SDH100RT) are **not listed**; any forward
produced by P06 is simulated, so ``provenance.simulated`` is derived from the carry model
(always ``True``) and never forgotten (rule ``forward-real-simulated``).

Anti look-ahead: only data ``<= t`` (P08 ``GuardedView``) feeds the signal at ``t``.
"""

from __future__ import annotations

import numpy as np

from core.backtest.protocols import PointInTimeView
from core.pricing.derivatives.carry import DEFAULT_RISK_FREE_RATE, CostOfCarryModel
from core.pricing.derivatives.futures import CarryFuturesPricer
from core.pricing.derivatives.protocols import CarryModel
from core.signals.protocols import SignalProvenance, clip_unit

#: Minimum number of basis changes required to estimate a rolling standard deviation.
_MIN_LOOKBACK: int = 2


class FuturesBasisSignal:
    """Carry/roll momentum on the future/spot basis (implements ``SignalProducer``).

    Parameters
    ----------
    tau_years : float
        Maturity ``tau`` (years) of the theoretical future used to compute the basis (``> 0``).
    lookback : int
        Rolling window of basis changes used for the z-score (``>= 2``).
    carry_model : CarryModel, optional
        Forward source; defaults to ``CostOfCarryModel()`` (P06 cost-of-carry).
    rate : float
        Annualised funding rate passed to the P06 pricer (implied yield, sensitivities).
    name : str
        Signal identifier (MLflow tracking / desk attribution).

    Raises
    ------
    ValueError
        If ``tau_years <= 0`` or ``lookback < 2``.
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
            raise ValueError(f"tau_years ({tau_years}) must be > 0.")
        if lookback < _MIN_LOOKBACK:
            raise ValueError(f"lookback ({lookback}) must be >= {_MIN_LOOKBACK}.")
        model: CarryModel = carry_model if carry_model is not None else CostOfCarryModel()
        self._pricer = CarryFuturesPricer(model, rate)
        self._tau = tau_years
        self.lookback = lookback
        self.name = name
        # Unlisted compute forward => simulated; the flag is derived from the model (never missed).
        self.provenance = SignalProvenance(name=name, simulated=model.simulated)

    def _basis(self, spot: float) -> float:
        """Theoretical basis ``F - S`` at this spot, via the P06 cost-of-carry pricer."""
        return self._pricer.price(spot, self._tau).basis

    def signal(self, view: PointInTimeView) -> float:
        """Target position at ``t``: z-score of the basis change over the window ``<= t``.

        ``lookback + 1`` prices are required (hence ``lookback`` changes); below that, or when
        the basis change has a zero standard deviation (constant prices), the signal stays flat
        (0) — there is nothing new to say.
        """
        history = view.history()
        if history.size < self.lookback + 1:
            return 0.0
        window_prices = history[-(self.lookback + 1) :]
        basis = np.array([self._basis(float(p)) for p in window_prices], dtype=np.float64)
        delta = np.diff(basis)  # length = lookback
        std = float(delta.std(ddof=1))
        if std == 0.0:
            return 0.0
        z = (float(delta[-1]) - float(delta.mean())) / std
        return clip_unit(z)


__all__ = ["FuturesBasisSignal"]
