"""Config régionale injectable + factory de pricer (P05).

Une région possède son **PUE**, son efficience matérielle (TDP, nombre de GPU) et son
taux de change $/€. Comme le PUE vit dans le ``PowerModel`` de P01 (pas dans l'appel
``price``), un PUE régional impose **un ``SparkSpreadPricer`` par région** : c'est le rôle
de ``build_regional_pricer``.

Aucun nombre magique dans la logique (rule python-quality) : les constantes régionales
sont des champs nommés de ``RegionConfig`` ; ``DEFAULT_REGIONS`` n'est qu'un jeu de défauts
documenté, surchargeable par injection.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.pricing import ConstantFx, ServerPowerModel, SparkSpreadPricer
from core.pricing.protocols import SpreadKernel


@dataclass(frozen=True)
class RegionConfig:
    """Paramètres d'une région pour le pricing du spark spread.

    Parameters
    ----------
    code
        Identifiant région (clé de la colonne énergie, ex. ``"FR"``, ``"DE"``).
    pue
        Power Usage Effectiveness (sans dimension, ≥ 1.0).
    tdp_w
        Puissance IT (TDP) d'un GPU, en watts (> 0).
    n_gpus
        Nombre de GPU du serveur de référence (> 0).
    fx_eur_per_usd
        Taux de change EUR par USD appliqué au revenu compute (> 0).
    label
        Étiquette lisible (datacentre / zone), traçabilité uniquement.
    """

    code: str
    pue: float
    tdp_w: float
    n_gpus: int
    fx_eur_per_usd: float
    label: str = ""

    def __post_init__(self) -> None:
        if self.pue < 1.0:
            raise ValueError(f"pue doit être ≥ 1.0 (reçu {self.pue}) : conso totale ≥ conso IT.")
        if self.tdp_w <= 0:
            raise ValueError(f"tdp_w doit être > 0 (reçu {self.tdp_w}).")
        if self.n_gpus <= 0:
            raise ValueError(f"n_gpus doit être > 0 (reçu {self.n_gpus}).")
        if self.fx_eur_per_usd <= 0:
            raise ValueError(f"fx_eur_per_usd doit être > 0 (reçu {self.fx_eur_per_usd}).")


def build_regional_pricer(
    cfg: RegionConfig, *, kernel: SpreadKernel | None = None
) -> SparkSpreadPricer:
    """Construit un ``SparkSpreadPricer`` (P01) portant le PUE/efficience de ``cfg``.

    Factory pure : aucune I/O. Le noyau Rust est injectable (défaut : oracle Python).
    """
    power_model = ServerPowerModel(tdp_w=cfg.tdp_w, pue=cfg.pue, n_gpus=cfg.n_gpus)
    return SparkSpreadPricer(power_model, ConstantFx(cfg.fx_eur_per_usd), kernel)


# Défauts documentés (config, pas magie) : H100 8-GPU, PUE FR < DE (mix nucléaire vs charbon/gaz),
# FX EUR/USD ~ parité. Surchargeables par injection dans run_basis.py / les tests.
DEFAULT_REGIONS: tuple[RegionConfig, ...] = (
    RegionConfig(code="FR", pue=1.20, tdp_w=700.0, n_gpus=8, fx_eur_per_usd=0.92, label="France"),
    RegionConfig(code="DE", pue=1.45, tdp_w=700.0, n_gpus=8, fx_eur_per_usd=0.92, label="Germany"),
)
