"""Dérivés théoriques sur le compute (futures non listés) — couche Stratégie P06.

⚠️ Frontière réel/simulé : les futures compute CME (settlement sur l'indice Silicon
Data SDH100RT) sont **annoncés mais non listés** (revue réglementaire). Tout prix
produit ici est donc **théorique/simulé** — la :class:`FuturesQuote` porte un champ
``simulated`` obligatoire (sans valeur par défaut), garanti par le type et testé.

Sous-paquet autonome de :mod:`core.pricing` : n'altère pas l'API P01 (spark spread).
La convergence ajoutera le re-export depuis ``core/pricing/__init__.py`` (cf.
``projects/06_compute_futures_pricing/CONVERGENCE.md``).
"""

from __future__ import annotations

from core.pricing.derivatives.carry import (
    DEFAULT_CONVENIENCE_YIELD,
    DEFAULT_RISK_FREE_RATE,
    CarrySensitivities,
    CostOfCarryModel,
    carry_forward,
    carry_sensitivities,
    implied_convenience_yield,
)
from core.pricing.derivatives.futures import CarryFuturesPricer, FuturesQuote
from core.pricing.derivatives.protocols import CarryModel, FuturesPricer

__all__ = [
    # Contrats (DI / SOLID).
    "CarryModel",
    "FuturesPricer",
    # Cœur cost-of-carry (fonctions pures).
    "carry_forward",
    "implied_convenience_yield",
    "carry_sensitivities",
    "CarrySensitivities",
    "CostOfCarryModel",
    "DEFAULT_RISK_FREE_RATE",
    "DEFAULT_CONVENIENCE_YIELD",
    # Orchestrateur + résultat.
    "CarryFuturesPricer",
    "FuturesQuote",
]
