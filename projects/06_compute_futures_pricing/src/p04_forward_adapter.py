"""Adapter: plugs P04's SIMULATED forward curve into the ``CarryModel`` contract.

Lives in the **project layer** (not in ``core/``) so as not to couple the
``core.pricing.derivatives`` core to ``projects/04``'s ``forward`` package —
``mypy core`` stays clean and the dependency direction is respected (core ignores projects).

P04 expresses maturities in **days** and ``kappa`` per day; the P06 core reasons
in **years** (annualized rates). The adapter carries the years → days conversion.
Since the Schwartz forward is a model, ``simulated`` is always ``True``.
"""

from __future__ import annotations

from dataclasses import dataclass

from forward.models import SchwartzParams
from forward.oracle import forward_price

#: Days per year to convert maturities (consistent with P04, 365.25 basis).
DAYS_PER_YEAR: float = 365.25


@dataclass(frozen=True)
class P04ForwardAdapter:
    """Exposes P04's analytic Schwartz forward as a ``CarryModel``.

    Parameters
    ----------
    params
        One-factor Schwartz parameters (calibrated by P04, ``kappa`` per day).
    days_per_year
        Years → days conversion factor used to query the P04 forward.
    """

    params: SchwartzParams
    days_per_year: float = DAYS_PER_YEAR

    @property
    def name(self) -> str:
        return "schwartz_p04"

    @property
    def simulated(self) -> bool:
        return True

    def forward(self, spot: float, tau_years: float) -> float:
        """P04 Schwartz forward price for ``tau_years`` (converted to days)."""
        return forward_price(spot, self.params, tau_years * self.days_per_year)
