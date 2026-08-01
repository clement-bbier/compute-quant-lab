"""Spark spread basis calculation between regions (P05) — PURE core, no I/O.

The ``BasisCalculator`` consumes a ``SparkSpreadPricer`` (P01) **per region** (injected,
DIP) and produces the point-in-time basis: ``basis[r] = spread[r] − spread[reference]``.

Anti look-ahead: each pricer already aligns compute on its energy grid via a backward
as-of join; here, regional spreads are aligned against each other via an **inner join**
(index intersection) — no value is fabricated or carried back from the future.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
import pandas as pd

from core.pricing import SparkSpreadPricer
from core.pricing.protocols import PriceSource


@dataclass(frozen=True)
class BasisResult:
    """Inter-region basis + aligned regional spreads and traceability metadata.

    Attributes
    ----------
    spreads
        Region → spread €/GPU·h, on the common grid (UTC).
    basis
        Region (≠ ``reference``) → ``spread[region] − spread[reference]`` (€/GPU·h).
    reference
        Reference region for the basis.
    regions
        All priced regions (injection order).
    pue
        Region → PUE used (regional assumption, traceability).
    window
        (first, last) UTC timestamp of the common grid.
    """

    spreads: Mapping[str, pd.Series]
    basis: Mapping[str, pd.Series]
    reference: str
    regions: tuple[str, ...]
    pue: Mapping[str, float]
    window: tuple[pd.Timestamp, pd.Timestamp]


class BasisCalculator:
    """Measures the spark spread basis between regions from injected pricers.

    Parameters
    ----------
    pricers
        Region → ``SparkSpreadPricer`` (one per region, carrying its PUE/efficiency).
    reference
        Reference region: each other region's basis is computed against it.
    """

    def __init__(self, pricers: Mapping[str, SparkSpreadPricer], *, reference: str) -> None:
        if len(pricers) < 2:
            raise ValueError("The basis requires at least two regions.")
        if reference not in pricers:
            raise ValueError(f"reference '{reference}' not found among the supplied pricers.")
        self._pricers: dict[str, SparkSpreadPricer] = dict(pricers)
        self._reference = reference

    def compute(self, source: PriceSource, gpu: str) -> BasisResult:
        """Price each region and compute the basis on the common grid (point-in-time)."""
        results = {
            region: pricer.price(source, gpu, region) for region, pricer in self._pricers.items()
        }
        # Inner join: keep only instants co-observed across all regions.
        spread_frame = pd.concat(
            {region: res.spread for region, res in results.items()}, axis=1, join="inner"
        )
        reference_spread = spread_frame[self._reference]
        regions = tuple(self._pricers)

        spreads = {region: spread_frame[region].rename(f"spread_{region}") for region in regions}
        basis = {
            region: (spread_frame[region] - reference_spread).rename(
                f"basis_{region}_{self._reference}"
            )
            for region in regions
            if region != self._reference
        }
        pue = {region: res.pue for region, res in results.items()}
        window = (spread_frame.index[0], spread_frame.index[-1])

        return BasisResult(
            spreads=spreads,
            basis=basis,
            reference=self._reference,
            regions=regions,
            pue=pue,
            window=window,
        )


@dataclass(frozen=True)
class DislocationSummary:
    """Summary of a basis's dislocations: amplitude, frequency, persistence.

    Attributes
    ----------
    threshold
        Dislocation threshold used (€/GPU·h).
    fraction_dislocated
        Fraction of time where ``|basis| > threshold`` (∈ [0, 1]).
    amplitude_p95
        95th percentile of ``|basis|`` (typical excursion magnitude, €/GPU·h).
    n_dislocations
        Number of contiguous episodes above the threshold.
    half_life_hours
        Mean-reversion half-life (AR(1)) in hours; ``None`` if the series is
        not mean-reverting (φ ∉ ]0, 1[).
    """

    threshold: float
    fraction_dislocated: float
    amplitude_p95: float
    n_dislocations: int
    half_life_hours: float | None


def _ar1_half_life_hours(basis: pd.Series) -> float | None:
    """AR(1) half-life in hours (hourly grid assumed); ``None`` if not mean-reverting.

    OLS regression ``basis_t = c + φ·basis_{t-1}``; half-life = ln(2) / −ln(φ) if φ ∈ ]0, 1[.
    """
    values = basis.to_numpy(dtype=float)
    previous, current = values[:-1], values[1:]
    phi = float(np.polyfit(previous, current, 1)[0])
    if not 0.0 < phi < 1.0:
        return None
    return float(np.log(2.0) / -np.log(phi))


def detect_dislocations(
    basis: pd.Series, *, z: float = 2.0, threshold: float | None = None
) -> DislocationSummary:
    """Quantifies a basis's dislocations (amplitude + frequency) and their persistence.

    Validated methodology (§3c): **threshold** for amplitude/frequency, **AR(1) half-life**
    for persistence. The half-life is delegated to :func:`_ar1_half_life_hours`.

    Parameters
    ----------
    basis
        Basis series (€/GPU·h), hourly UTC index. NaNs are ignored.
    z
        Z-score factor for the automatic threshold (``threshold = z · std``) if
        ``threshold`` is not supplied.
    threshold
        Explicit dislocation threshold in €/GPU·h (takes priority over ``z``).

    Returns
    -------
    DislocationSummary
    """
    clean = basis.dropna()
    abs_basis = clean.abs()
    used_threshold = threshold if threshold is not None else z * float(clean.std())

    dislocated = abs_basis > used_threshold
    fraction = float(dislocated.mean())
    amplitude_p95 = float(abs_basis.quantile(0.95))
    # Number of contiguous episodes = False→True transitions, + the "dislocated from t₀" case.
    starts = dislocated.astype(int).diff()
    n_dislocations = int((starts == 1).sum()) + int(bool(dislocated.iloc[0]))

    return DislocationSummary(
        threshold=used_threshold,
        fraction_dislocated=fraction,
        amplitude_p95=amplitude_p95,
        n_dislocations=n_dislocations,
        half_life_hours=_ar1_half_life_hours(clean),
    )
