"""Pricer vectoriel du digital spark spread (orchestration DI/SOLID).

`SparkSpreadPricer` dépend d'abstractions (`PriceSource`, `PowerModel`,
`FxConverter`, `SpreadKernel`), jamais d'implémentations concrètes (DIP). Il
reste une **fonction pure** : aucune I/O cachée, tout effet de bord (réseau,
disque) vit dans `projects/01_.../src/`.

Sélection du noyau par injection : Rust si fourni, sinon l'oracle Python. Le
subcrate Rust (`core.pricing._kernel`) est optionnel ; son absence ne dégrade
que la performance, jamais le résultat.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from core.pricing.efficiency import tflops_fp16
from core.pricing.oracle import PythonOracle
from core.pricing.power_model import ServerPowerModel
from core.pricing.protocols import (
    FloatArray,
    FxConverter,
    PowerModel,
    PriceSource,
    SpreadKernel,
)


@dataclass(frozen=True)
class SpreadResult:
    """Résultat du pricing : décomposition revenu/coût + métadonnées.

    La décomposition explicite (`revenue`, `cost`, `spread`) répond à l'exigence
    du prompt P01 §3a ; les métadonnées tracent les hypothèses du calcul.
    """

    spread: pd.Series
    revenue: pd.Series
    cost: pd.Series
    gpu: str
    region: str
    pue: float
    power_kw_per_gpu: float
    fx: str
    window: tuple[pd.Timestamp, pd.Timestamp]


class RustKernel:
    """Adaptateur du subcrate Rust optionnel vers le protocole `SpreadKernel`.

    Instanciable seulement si `core.pricing._kernel` est compilé (``maturin
    develop``) ; lève `ImportError` sinon.
    """

    def __init__(self) -> None:
        import importlib  # noqa: PLC0415 (import optionnel runtime)

        kernel = importlib.import_module("core.pricing._kernel")
        self._compute = kernel.compute

    def compute(
        self,
        compute_eur_per_gpu_h: FloatArray,
        energy_eur_per_mwh: FloatArray,
        power_kw_per_gpu: FloatArray,
        pue: FloatArray,
    ) -> tuple[FloatArray, FloatArray, FloatArray]:
        return self._compute(  # type: ignore[no-any-return]
            np.ascontiguousarray(compute_eur_per_gpu_h, dtype=np.float64),
            np.ascontiguousarray(energy_eur_per_mwh, dtype=np.float64),
            np.ascontiguousarray(power_kw_per_gpu, dtype=np.float64),
            np.ascontiguousarray(pue, dtype=np.float64),
        )


class SparkSpreadPricer:
    """Price le digital spark spread sur une grille temporelle, point-in-time.

    Parameters
    ----------
    power_model
        Modèle de puissance/PUE (abstraction `PowerModel`).
    fx
        Convertisseur $/€ (abstraction `FxConverter`).
    kernel
        Noyau de calcul (abstraction `SpreadKernel`). Défaut : oracle Python.
    """

    def __init__(
        self,
        power_model: PowerModel,
        fx: FxConverter,
        kernel: SpreadKernel | None = None,
    ) -> None:
        self._power_model = power_model
        self._fx = fx
        self._kernel: SpreadKernel = kernel if kernel is not None else PythonOracle()

    def price(self, source: PriceSource, gpu: str, region: str) -> SpreadResult:
        """Calcule le spread €/GPU·h sur la grille de la jambe énergie.

        L'énergie (historique profond) porte la grille d'évaluation ; le compute
        est aligné dessus par jointure as-of **arrière** (dernier prix connu à
        chaque instant) — aucun prix futur n'entre dans le spread à ``t``.
        """
        return self._price_at_pue(source, gpu, region, self._power_model.pue())

    def _price_at_pue(self, source: PriceSource, gpu: str, region: str, pue: float) -> SpreadResult:
        """Chemin de pricing central, paramétré par le PUE (réutilisé par les bandes)."""
        energy = source.energy_price(region)
        compute_usd = source.compute_price(gpu)
        compute_eur = self._fx.to_eur(compute_usd).sort_index()

        grid = energy.sort_index().index
        # ffill = report de la dernière valeur d'index ≤ t : as-of arrière strict.
        compute_on_grid = compute_eur.reindex(grid, method="ffill")

        power_kw = self._power_model.power_kw_per_gpu()
        n = len(grid)
        revenue_a, cost_a, spread_a = self._kernel.compute(
            compute_on_grid.to_numpy(dtype=np.float64),
            energy.reindex(grid).to_numpy(dtype=np.float64),
            np.full(n, power_kw, dtype=np.float64),
            np.full(n, pue, dtype=np.float64),
        )

        return SpreadResult(
            spread=pd.Series(spread_a, index=grid, name="spread"),
            revenue=pd.Series(revenue_a, index=grid, name="revenue"),
            cost=pd.Series(cost_a, index=grid, name="cost"),
            gpu=gpu,
            region=region,
            pue=pue,
            power_kw_per_gpu=power_kw,
            fx=repr(self._fx),
            window=(grid[0], grid[-1]),
        )

    def normalized_spread(self, res: SpreadResult) -> pd.Series:
        """Spread ramené à l'unité de compte : €/GPU·h **par TFLOP** (FP16 dense).

        Rend le spread comparable entre GPU d'efficacités différentes.
        """
        return (res.spread / tflops_fp16(res.gpu)).rename("normalized_spread")

    def pue_sensitivity(
        self, source: PriceSource, gpu: str, region: str
    ) -> tuple[SpreadResult, SpreadResult]:
        """Re-price aux bornes du prior PUE → bande ``(low_pue, high_pue)``.

        Exige un `ServerPowerModel` construit avec un `PuePrior`. Le chemin central
        `price()` n'est pas touché (parité préservée).
        """
        pm = self._power_model
        bounds = pm.pue_bounds() if isinstance(pm, ServerPowerModel) else None
        if bounds is None:
            raise ValueError("pue_sensitivity exige un ServerPowerModel construit avec un PuePrior")
        low, high = bounds
        return (
            self._price_at_pue(source, gpu, region, low),
            self._price_at_pue(source, gpu, region, high),
        )
