"""Pricing du digital spark spread.

Expose la brique scalaire historique (réutilisée par l'oracle comme référence
chiffrée) et le pricer vectoriel point-in-time DI/SOLID.
"""

from core.pricing.fx import ConstantFx, SeriesFx
from core.pricing.oracle import PythonOracle
from core.pricing.power_model import ServerPowerModel
from core.pricing.pricer import SparkSpreadPricer, SpreadResult
from core.pricing.protocols import (
    FloatArray,
    FxConverter,
    PowerModel,
    PriceSource,
    SpreadKernel,
)
from core.pricing.sources import DataFramePriceSource
from core.pricing.spark_spread import (
    ServerSpec,
    energy_cost_per_gpu_hour,
    spark_spread_per_gpu_hour,
)

# Sous-paquet dérivés (P06) — futures compute théoriques/simulés.
from core.pricing import derivatives
from core.pricing.derivatives import CarryFuturesPricer, FuturesQuote

__all__ = [
    # Brique scalaire de référence (API inchangée).
    "ServerSpec",
    "energy_cost_per_gpu_hour",
    "spark_spread_per_gpu_hour",
    # Pricer vectoriel.
    "SparkSpreadPricer",
    "SpreadResult",
    "ServerPowerModel",
    "ConstantFx",
    "SeriesFx",
    "DataFramePriceSource",
    "PythonOracle",
    # Contrats (abstractions).
    "PriceSource",
    "PowerModel",
    "FxConverter",
    "SpreadKernel",
    "FloatArray",
    # Dérivés (P06).
    "derivatives",
    "CarryFuturesPricer",
    "FuturesQuote",
]
