"""Stratégies concrètes d'agrégation de l'indice spot compute.

Chaque classe satisfait structurellement un protocole de ``protocols.py`` :

- :class:`OutlierFilter` → :class:`MadOutlierFilter`, :class:`NoOutlierFilter` ;
- :class:`IndexEstimator` → :class:`TrimmedMean`, :class:`Median`,
  :class:`AvailabilityWeightedMean`.

Ajouter une méthode d'agrégation = ajouter une classe ici, sans modifier le cœur
``build_spot_index`` (Open/Closed). Calcul en NumPy uniquement (dépendance déjà
déclarée), pas de SciPy requis.

Défauts du marché (cf. GPU Markets / Silicon Data) : trimmed mean 20 % + rejet à
2.5 MAD — assemblés dans ``DEFAULT_INDEX_CONFIG`` (voir ``compute_index.py``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from core.ingestion.protocols import VenueRate


@dataclass(frozen=True)
class NoOutlierFilter:
    """Filtre identité : conserve tous les taux (rejet d'outliers désactivé)."""

    @property
    def name(self) -> str:
        return "nofilter"

    def filter(self, rates: Sequence[VenueRate]) -> list[VenueRate]:
        return list(rates)


@dataclass(frozen=True)
class MadOutlierFilter:
    """Rejette les taux à plus de ``k`` écarts absolus médians (MAD) de la médiane.

    Méthode robuste standard (insensible aux valeurs extrêmes, contrairement à
    l'écart-type). Un MAD nul (taux tous égaux) conserve tout.

    Parameters
    ----------
    k
        Multiplicateur du MAD au-delà duquel un taux est rejeté. Défaut marché : 2.5.
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
    """Moyenne tronquée : retire ``trim`` à chaque extrémité, puis moyenne le reste.

    Parameters
    ----------
    trim
        Proportion retirée à chaque queue (0.20 = 20 % en haut et en bas). Si trop
        peu de points pour tronquer (k = 0), équivaut à une moyenne simple.
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
    """Médiane des taux par-venue (équipondérée, robuste)."""

    @property
    def name(self) -> str:
        return "median"

    def estimate(self, rates: Sequence[VenueRate]) -> float:
        return float(np.median(np.array([r.rate for r in rates], dtype=float)))


@dataclass(frozen=True)
class AvailabilityWeightedMean:
    """Moyenne pondérée par la disponibilité (volume d'offres) de chaque venue.

    Représentative du marché mais sensible à une grosse venue. Si toutes les
    disponibilités sont nulles, retombe sur une moyenne équipondérée.
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
