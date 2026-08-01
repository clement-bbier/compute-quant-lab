"""Concrete aggregation strategies for the compute spot index.

Each class structurally satisfies one of the protocols in ``protocols.py``:

- :class:`OutlierFilter` -> :class:`MadOutlierFilter`, :class:`NoOutlierFilter`;
- :class:`IndexEstimator` -> :class:`TrimmedMean`, :class:`Median`,
  :class:`AvailabilityWeightedMean`.

Adding an aggregation method means adding a class here, without modifying the
``build_spot_index`` core (Open/Closed). Computation uses NumPy only (an already
declared dependency), no SciPy required.

Market defaults (see GPU Markets / Silicon Data): 20 % trimmed mean + rejection at
2.5 MAD -- assembled in ``DEFAULT_INDEX_CONFIG`` (see ``compute_index.py``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from core.ingestion.protocols import VenueRate


@dataclass(frozen=True)
class NoOutlierFilter:
    """Identity filter: keeps every rate (outlier rejection disabled)."""

    @property
    def name(self) -> str:
        return "nofilter"

    def filter(self, rates: Sequence[VenueRate]) -> list[VenueRate]:
        return list(rates)


@dataclass(frozen=True)
class MadOutlierFilter:
    """Reject rates further than ``k`` median absolute deviations (MAD) from the median.

    Standard robust method (insensitive to extreme values, unlike the standard deviation).
    A zero MAD (all rates equal) keeps everything.

    Parameters
    ----------
    k
        MAD multiplier beyond which a rate is rejected. Market default: 2.5.
    """

    k: float = 2.5

    @property
    def name(self) -> str:
        return f"mad{self.k}"

    def filter(self, rates: Sequence[VenueRate]) -> list[VenueRate]:
        values = np.array([r.rate for r in rates], dtype=float)
        median = float(np.median(values))
        mad = float(np.median(np.abs(values - median)))
        if mad == 0.0:
            return list(rates)
        keep = np.abs(values - median) <= self.k * mad
        return [r for r, ok in zip(rates, keep) if ok]


@dataclass(frozen=True)
class TrimmedMean:
    """Trimmed mean: drop ``trim`` at each end, then average the remainder.

    Parameters
    ----------
    trim
        Proportion removed from each tail (0.20 = 20 % at the top and at the bottom).
        With too few points to trim (k = 0), this is equivalent to a plain mean.
    """

    trim: float = 0.20

    @property
    def name(self) -> str:
        return f"trimmed_mean{int(round(self.trim * 100))}"

    def estimate(self, rates: Sequence[VenueRate]) -> float:
        values = np.sort(np.array([r.rate for r in rates], dtype=float))
        n = values.size
        k = int(np.floor(self.trim * n))
        core = values[k : n - k] if n - 2 * k > 0 else values
        return float(np.mean(core))


@dataclass(frozen=True)
class Median:
    """Median of the per-venue rates (equally weighted, robust)."""

    @property
    def name(self) -> str:
        return "median"

    def estimate(self, rates: Sequence[VenueRate]) -> float:
        return float(np.median(np.array([r.rate for r in rates], dtype=float)))


@dataclass(frozen=True)
class AvailabilityWeightedMean:
    """Mean weighted by each venue's availability (offer volume).

    Representative of the market but sensitive to one large venue. If every availability
    is zero, falls back to an equally weighted mean.
    """

    @property
    def name(self) -> str:
        return "avail_weighted"

    def estimate(self, rates: Sequence[VenueRate]) -> float:
        values = np.array([r.rate for r in rates], dtype=float)
        weights = np.array([r.availability for r in rates], dtype=float)
        if weights.sum() <= 0:
            return float(np.mean(values))
        return float(np.average(values, weights=weights))
