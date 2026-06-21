"""Calcul du basis du spark spread entre régions (P05) — cœur PUR, aucune I/O.

Le ``BasisCalculator`` consomme un ``SparkSpreadPricer`` (P01) **par région** (injecté,
DIP) et produit le basis point-in-time : ``basis[r] = spread[r] − spread[reference]``.

Anti look-ahead : chaque pricer aligne déjà le compte sur sa grille énergie par jointure
as-of arrière ; ici, les spreads régionaux sont alignés entre eux par **jointure interne**
(intersection d'index) — aucune valeur n'est fabriquée ni reportée depuis le futur.
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
    """Basis inter-régions + spreads régionaux alignés et métadonnées de traçabilité.

    Attributes
    ----------
    spreads
        Région → spread €/GPU·h, sur la grille commune (UTC).
    basis
        Région (≠ ``reference``) → ``spread[région] − spread[reference]`` (€/GPU·h).
    reference
        Région de référence du basis.
    regions
        Toutes les régions pricées (ordre d'injection).
    pue
        Région → PUE retenu (hypothèse régionale, traçabilité).
    window
        (premier, dernier) timestamp UTC de la grille commune.
    """

    spreads: Mapping[str, pd.Series]
    basis: Mapping[str, pd.Series]
    reference: str
    regions: tuple[str, ...]
    pue: Mapping[str, float]
    window: tuple[pd.Timestamp, pd.Timestamp]


class BasisCalculator:
    """Mesure le basis du spark spread entre régions à partir de pricers injectés.

    Parameters
    ----------
    pricers
        Région → ``SparkSpreadPricer`` (un par région, portant son PUE/efficience).
    reference
        Région de référence : le basis de chaque autre région est calculé contre elle.
    """

    def __init__(self, pricers: Mapping[str, SparkSpreadPricer], *, reference: str) -> None:
        if len(pricers) < 2:
            raise ValueError("Le basis exige au moins deux régions.")
        if reference not in pricers:
            raise ValueError(f"reference '{reference}' absente des pricers fournis.")
        self._pricers: dict[str, SparkSpreadPricer] = dict(pricers)
        self._reference = reference

    def compute(self, source: PriceSource, gpu: str) -> BasisResult:
        """Price chaque région et calcule le basis sur la grille commune (point-in-time)."""
        results = {
            region: pricer.price(source, gpu, region) for region, pricer in self._pricers.items()
        }
        # Jointure interne : ne garde que les instants co-observés par toutes les régions.
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
    """Synthèse des dislocations d'un basis : amplitude, fréquence, persistance.

    Attributes
    ----------
    threshold
        Seuil de dislocation retenu (€/GPU·h).
    fraction_dislocated
        Part du temps où ``|basis| > threshold`` (∈ [0, 1]).
    amplitude_p95
        95ᵉ percentile de ``|basis|`` (ampleur typique des excursions, €/GPU·h).
    n_dislocations
        Nombre d'épisodes contigus au-dessus du seuil.
    half_life_hours
        Demi-vie de retour à la moyenne (AR(1)) en heures ; ``None`` si la série
        n'est pas mean-reverting (φ ∉ ]0, 1[).
    """

    threshold: float
    fraction_dislocated: float
    amplitude_p95: float
    n_dislocations: int
    half_life_hours: float | None


def _ar1_half_life_hours(basis: pd.Series) -> float | None:
    """Demi-vie AR(1) en heures (grille horaire supposée) ; ``None`` si non mean-reverting.

    Régression OLS ``basis_t = c + φ·basis_{t-1}`` ; demi-vie = ln(2) / −ln(φ) si φ ∈ ]0, 1[.
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
    """Quantifie les dislocations d'un basis (amplitude + fréquence) et leur persistance.

    Méthodologie validée (§3c) : **seuil** pour l'amplitude/fréquence, **demi-vie AR(1)**
    pour la persistance. La demi-vie est déléguée à :func:`_ar1_half_life_hours`.

    Parameters
    ----------
    basis
        Série du basis (€/GPU·h), index UTC horaire. Les NaN sont ignorés.
    z
        Facteur z-score pour le seuil automatique (``threshold = z · std``) si ``threshold``
        n'est pas fourni.
    threshold
        Seuil de dislocation explicite en €/GPU·h (prioritaire sur ``z``).

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
    # Nombre d'épisodes contigus = transitions False→True, + le cas « disloqué dès t₀ ».
    starts = dislocated.astype(int).diff()
    n_dislocations = int((starts == 1).sum()) + int(bool(dislocated.iloc[0]))

    return DislocationSummary(
        threshold=used_threshold,
        fraction_dislocated=fraction,
        amplitude_p95=amplitude_p95,
        n_dislocations=n_dislocations,
        half_life_hours=_ar1_half_life_hours(clean),
    )
