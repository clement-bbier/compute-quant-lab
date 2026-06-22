"""Modèle énergétique d'un serveur GPU.

Sépare proprement la puissance *IT* (TDP des GPU) de l'efficacité du datacenter
(PUE), là où la brique scalaire historique (`spark_spread.py`) ne manipulait
qu'une puissance « PUE incluse ». Cette séparation rend explicite le levier PUE
exigé par l'étude de sensibilité du prompt P01.
"""

from __future__ import annotations

from core.pricing.pue_prior import PuePrior

WATTS_PER_KILOWATT: float = 1000.0


class ServerPowerModel:
    """Modèle de puissance d'un serveur multi-GPU (implémente `PowerModel`).

    Calibré par défaut sur la thèse : 8x H100 à 700 W de TDP et PUE 1.82
    reproduisent les ~10.2 kW serveur (et ~0.19 €/h/GPU à 150 €/MWh) de la
    brique de référence.

    Parameters
    ----------
    tdp_w
        Puissance IT (TDP) d'un GPU, en watts.
    pue
        Power Usage Effectiveness du datacenter (sans dimension, ≥ 1). Accepte un
        scalaire ``float`` ou un ``PuePrior`` (region-keyed) : dans ce dernier cas
        le pricing central utilise le *point estimate* et expose les bornes via
        ``pue_bounds()``.
    n_gpus
        Nombre de GPU du serveur (métadonnée, agrégation au niveau serveur).
    """

    def __init__(self, tdp_w: float, pue: float | PuePrior, n_gpus: int) -> None:
        if tdp_w <= 0:
            raise ValueError("tdp_w doit être strictement positif")
        if n_gpus <= 0:
            raise ValueError("n_gpus doit être strictement positif")
        if isinstance(pue, PuePrior):
            self._pue_value = pue.point_estimate()
            self._pue_prior: PuePrior | None = pue
        else:
            if pue < 1.0:
                raise ValueError("pue doit être ≥ 1.0 (le datacenter consomme ≥ l'IT)")
            self._pue_value = pue
            self._pue_prior = None
        self._tdp_w = tdp_w
        self._n_gpus = n_gpus

    def power_kw_per_gpu(self) -> float:
        """Puissance IT par GPU en kW (hors refroidissement, le PUE l'ajoute)."""
        return self._tdp_w / WATTS_PER_KILOWATT

    def pue(self) -> float:
        """Power Usage Effectiveness du datacenter (point estimate si prior)."""
        return self._pue_value

    def pue_bounds(self) -> tuple[float, float] | None:
        """Bornes de sensibilité [low, high] si un `PuePrior` est fourni, sinon None."""
        return self._pue_prior.sensitivity_bounds() if self._pue_prior else None

    @property
    def n_gpus(self) -> int:
        """Nombre de GPU du serveur."""
        return self._n_gpus

    def __repr__(self) -> str:
        return (
            f"ServerPowerModel(tdp_w={self._tdp_w}, pue={self._pue_value}, "
            f"n_gpus={self._n_gpus})"
        )
