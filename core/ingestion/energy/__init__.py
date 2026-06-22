"""Sous-paquet ``energy`` : fondation multi-marché pluggable pour l'ingestion énergie.

Registre de marchés énergétiques, calqué sur ``core.ingestion.providers``.
Chaque marché expose :class:`~core.ingestion.energy.base.EnergyMarket`
(prix RTM + prévision de réserve point-in-time).

Premier marché branché : ERCOT (Texas), 100 % réel via ``gridstatus``.

Registre des sources :
    - Unité      : $/MWh (RTM), MW (prévision de charge/capacité)
    - Fuseau     : UTC en interne (conversion depuis US/Central assurée par les connecteurs)
    - Fréquence  : RTM = intervalles 15 min ; prévisions = horaires
    - Limites    : ERCOT géoblocase l'API depuis certains réseaux hors US (WAF Imperva).
                   Le smoke live est conditionné à un accès réseau vers ercot.com.
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
