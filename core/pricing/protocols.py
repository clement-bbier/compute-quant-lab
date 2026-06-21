"""Contrats (abstractions) du pricer du digital spark spread.

Le `SparkSpreadPricer` dépend de ces `Protocol`, jamais d'implémentations
concrètes (Dependency Inversion Principle). Toute source de prix, modèle de
puissance, convertisseur FX ou noyau de calcul interchangeable se conforme à
l'un de ces contrats — ce qui rend le pricer testable avec des mocks et permet
de substituer le noyau Rust à l'oracle Python par simple injection.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np
import numpy.typing as npt
import pandas as pd

#: Tableau de flottants 64 bits, unité de travail du noyau vectoriel.
FloatArray = npt.NDArray[np.float64]


@runtime_checkable
class PriceSource(Protocol):
    """Fournit les deux jambes de prix, indexées en UTC, point-in-time.

    Les séries retournées sont déjà calées sur le *connu à t* : une valeur à
    l'instant ``t`` n'utilise aucune information publiée après ``t`` (la source
    applique elle-même le décalage de publication éventuel).
    """

    def energy_price(self, region: str) -> pd.Series:
        """Prix spot de l'électricité en €/MWh (index UTC tz-aware)."""
        ...

    def compute_price(self, gpu: str) -> pd.Series:
        """Prix de location du compute en $/GPU·h (index UTC tz-aware)."""
        ...


@runtime_checkable
class PowerModel(Protocol):
    """Modèle énergétique d'un GPU : puissance IT et efficacité datacenter."""

    def power_kw_per_gpu(self) -> float:
        """Puissance IT moyenne par GPU en kW (TDP, hors refroidissement)."""
        ...

    def pue(self) -> float:
        """Power Usage Effectiveness (conso totale / conso IT), sans dimension."""
        ...


@runtime_checkable
class FxConverter(Protocol):
    """Conversion $/€ point-in-time."""

    def to_eur(self, amount_usd: pd.Series) -> pd.Series:
        """Convertit une série en USD vers EUR au taux connu à chaque timestamp.

        Le résultat est aligné sur ``amount_usd.index`` ; chaque montant est
        converti avec le taux FX *connu à* son timestamp (anti look-ahead).
        """
        ...


@runtime_checkable
class SpreadKernel(Protocol):
    """Noyau de calcul vectoriel du spread, interchangeable (Python ou Rust).

    Toute implémentation produit un résultat strictement identique sur les
    mêmes entrées (l'oracle Python sert de référence à la parité du Rust).
    """

    def compute(
        self,
        compute_eur_per_gpu_h: FloatArray,
        energy_eur_per_mwh: FloatArray,
        power_kw_per_gpu: FloatArray,
        pue: FloatArray,
    ) -> tuple[FloatArray, FloatArray, FloatArray]:
        """Calcule ``(revenu, coût, spread)`` élément par élément.

        Parameters
        ----------
        compute_eur_per_gpu_h
            Revenu du compute en €/GPU·h (déjà converti depuis l'USD).
        energy_eur_per_mwh
            Prix de l'électricité en €/MWh.
        power_kw_per_gpu
            Puissance IT par GPU en kW.
        pue
            Power Usage Effectiveness.

        Returns
        -------
        tuple of FloatArray
            ``revenu`` (= compute), ``coût`` (énergétique), ``spread`` (= revenu − coût),
            chacun de la même longueur que les entrées.
        """
        ...
