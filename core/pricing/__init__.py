"""Digital spark spread pricing.

Exposes the historical scalar building block (reused by the oracle as a numeric
reference) and the point-in-time DI/SOLID vectorised pricer.
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

# Derivatives subpackage (P06) -- theoretical/simulated compute futures.
from core.pricing import derivatives
from core.pricing.derivatives import CarryFuturesPricer, FuturesQuote

__all__ = [
    # Reference scalar building block (API unchanged).
    "ServerSpec",
    "energy_cost_per_gpu_hour",
    "spark_spread_per_gpu_hour",
    # Vectorised pricer.
    "SparkSpreadPricer",
    "SpreadResult",
    "ServerPowerModel",
    "ConstantFx",
    "SeriesFx",
    "DataFramePriceSource",
    "PythonOracle",
    # Contracts (abstractions).
    "PriceSource",
    "PowerModel",
    "FxConverter",
    "SpreadKernel",
    "FloatArray",
    # Derivatives (P06).
    "derivatives",
    "CarryFuturesPricer",
    "FuturesQuote",
]
