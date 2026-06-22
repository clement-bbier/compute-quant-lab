"""Connecteur marketplace GPU — **shim de compatibilité** (la logique vit dans ``providers/``).

Historiquement Vast.ai et RunPod étaient implémentés ici. Pour ajouter des venues en
parallèle sans collision (*1 fichier = 1 venue*), la logique a migré dans le paquet
pluggable :mod:`core.ingestion.providers` (un module par venue + un protocole + un registre
key-gated). Ce module reste l'**API publique stable** :

- il **ré-exporte** les symboles historiques (``normalize_gpu_model``, ``parse_*``,
  ``fetch_*``) pour ne casser aucun importateur existant (façade ``core.ingestion``,
  tests P04) ;
- ``fetch_live_gpu_prices`` **délègue au registre** :func:`core.ingestion.providers.fetch_all`,
  en conservant sa signature et son comportement exacts (le collecteur planifié
  ``infra/collectors/gpu_price_snapshot.py`` et la collecte live GitHub Actions en dépendent).

Unité de sortie : USD par GPU·heure. Type de bail : on-demand.
"""

from __future__ import annotations

import datetime as dt

from core.ingestion.protocols import Snapshot
from core.ingestion.providers import fetch_all
from core.ingestion.providers.base import normalize_gpu_model
from core.ingestion.providers.runpod import fetch_runpod, parse_runpod_gpu_types
from core.ingestion.providers.vastai import fetch_vastai, parse_vastai_offers


def fetch_live_gpu_prices(now: dt.datetime | None = None) -> list[Snapshot]:
    """Relève le prix live de toutes les marketplaces configurées (par token ``.env``).

    Cible appelée par le collecteur planifié. Délègue au registre pluggable
    :func:`core.ingestion.providers.fetch_all` (key-gated : une venue sans clé est sautée).

    Raises
    ------
    RuntimeError
        Si aucune source n'est configurée (aucun token marketplace dans l'environnement).
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    snapshots = fetch_all(now)
    if not snapshots:
        raise RuntimeError(
            "Aucune source marketplace configurée : définir VASTAI_API_KEY ou "
            "RUNPOD_API_KEY (cf. .env / .env.example)."
        )
    return snapshots


#: Symboles historiques ré-exportés (compat ascendante : ne pas retirer sans convergence).
__all__ = [
    "normalize_gpu_model",
    "parse_vastai_offers",
    "fetch_vastai",
    "parse_runpod_gpu_types",
    "fetch_runpod",
    "fetch_live_gpu_prices",
]
