"""``energy`` subpackage: pluggable multi-market foundation for energy ingestion.

Registry of energy markets, modelled on ``core.ingestion.providers``.
Each market exposes :class:`~core.ingestion.energy.base.EnergyMarket`
(RTM price + point-in-time reserve forecast).

First market wired in: ERCOT (Texas), 100 % real via ``gridstatus``.

Source registry:
    - Unit       : $/MWh (RTM), MW (load/capacity forecast)
    - Timezone   : UTC internally (conversion from US/Central handled by the connectors)
    - Frequency  : RTM = 15 min intervals; forecasts = hourly
    - Limits     : ERCOT geoblocks the API from some non-US networks (Imperva WAF).
                   The live smoke test requires network access to ercot.com.
"""

from core.ingestion.energy.base import (
    EnergyMarket,
    available_markets,
    get_market,
    register_market,
)

__all__ = [
    "EnergyMarket",
    "available_markets",
    "get_market",
    "register_market",
]
