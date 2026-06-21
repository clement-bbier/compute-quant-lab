"""Digital spark spread : traduit l'électricité en coût de compute, et compare
ce coût marginal au prix de marché du compute pour en déduire une marge.

Formule de référence (cf. thèse du labo) :
    Un serveur de 8x Nvidia H100 consomme ~10.2 kW (refroidissement inclus, via le PUE).
    À 150 €/MWh, l'énergie coûte ~1.53 €/h pour le serveur, soit ~0.19 €/h par GPU.
"""

from __future__ import annotations

from dataclasses import dataclass

# --- Constantes physiques par défaut (surchargeables, jamais codées en dur ailleurs) ---
DEFAULT_GPUS_PER_SERVER: int = 8
DEFAULT_SERVER_POWER_KW: float = 10.2  # kW pour 8x H100, PUE inclus
MWH_TO_KWH: float = 1000.0


@dataclass(frozen=True)
class ServerSpec:
    """Caractéristiques énergétiques d'un serveur GPU."""

    n_gpus: int = DEFAULT_GPUS_PER_SERVER
    total_power_kw: float = DEFAULT_SERVER_POWER_KW

    @property
    def power_kw_per_gpu(self) -> float:
        """Puissance moyenne consommée par GPU (kW), refroidissement inclus."""
        return self.total_power_kw / self.n_gpus


def energy_cost_per_gpu_hour(
    electricity_price_eur_per_mwh: float,
    spec: ServerSpec | None = None,
) -> float:
    """Coût énergétique marginal d'une heure-GPU, en euros.

    Parameters
    ----------
    electricity_price_eur_per_mwh
        Prix spot de l'électricité (€/MWh), p. ex. issu d'ENTSO-E.
    spec
        Spécification du serveur. Par défaut : 8x H100 à 10.2 kW (PUE inclus).

    Returns
    -------
    float
        Coût énergétique en €/h/GPU. À 150 €/MWh : ~0.19 €/h/GPU.
    """
    spec = spec or ServerSpec()
    price_eur_per_kwh = electricity_price_eur_per_mwh / MWH_TO_KWH
    return spec.power_kw_per_gpu * price_eur_per_kwh


def spark_spread_per_gpu_hour(
    compute_price_eur_per_gpu_hour: float,
    electricity_price_eur_per_mwh: float,
    spec: ServerSpec | None = None,
) -> float:
    """Marge brute d'une heure-GPU : prix de marché du compute − coût énergétique.

    Un spread positif = produire du compute est rentable au prix d'énergie courant.
    C'est le signal de base de l'arbitrage énergie vs compute.
    """
    cost = energy_cost_per_gpu_hour(electricity_price_eur_per_mwh, spec)
    return compute_price_eur_per_gpu_hour - cost
