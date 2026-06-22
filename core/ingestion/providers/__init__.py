"""Registre pluggable des marketplaces GPU — **1 fichier = 1 venue** (OCP).

Chaque venue (Vast.ai, RunPod, …) vit dans son propre module et expose une classe
satisfaisant le protocole :class:`~core.ingestion.providers.base.GpuPriceProvider`. Le
registre :data:`PROVIDERS` les liste ; :func:`fetch_all` n'appelle que ceux dont **toutes**
les ``required_env`` sont présentes (key-gated), sinon loggue un avertissement et saute.

Ajouter une venue (pour la vague W2) — **3 étapes, sans toucher au cœur** :

1. Créer ``core/ingestion/providers/<venue>.py`` : ``parse_<venue>`` (pur) + ``fetch_<venue>``
   (I/O réseau, token-gated) + une classe ``<Venue>Provider`` avec ``name``, ``required_env``
   et ``fetch(now) -> list[Snapshot]`` (réutiliser ``base.normalize_gpu_model``).
2. Ajouter ``<Venue>Provider()`` au tuple :data:`PROVIDERS` ci-dessous.
3. Écrire un test de parité sous ``tests/`` (parse → ``Snapshot`` attendus) ; en convergence,
   ajouter la clé aux Secrets GitHub pour le collecteur always-on.

Aucune autre couche ne change : ``fetch_live_gpu_prices`` (shim ``gpu_market``) et le
collecteur agrègent automatiquement la nouvelle venue dès qu'une clé est configurée.
"""

from __future__ import annotations

import datetime as dt
import logging
import os

from core.ingestion.protocols import Snapshot
from core.ingestion.providers.base import GpuPriceProvider
from core.ingestion.providers.cudo import CudoProvider
from core.ingestion.providers.datacrunch import DatacrunchProvider
from core.ingestion.providers.hyperstack import HyperstackProvider
from core.ingestion.providers.primeintellect import PrimeintellectProvider
from core.ingestion.providers.runpod import RunpodProvider
from core.ingestion.providers.tensordock import TensordockProvider
from core.ingestion.providers.vastai import VastaiProvider

logger = logging.getLogger(__name__)

#: Venues enregistrées (7 actives). L'ordre fixe l'ordre d'agrégation des relevés :
#: la fondation W1 (Vast.ai, RunPod) puis les venues W2. Chacune est key-gated dans
#: :func:`fetch_all` ; une venue sans clé est simplement sautée (avertissement loggué).
PROVIDERS: tuple[GpuPriceProvider, ...] = (
    VastaiProvider(),
    RunpodProvider(),
    PrimeintellectProvider(),
    DatacrunchProvider(),
    CudoProvider(),
    HyperstackProvider(),
    TensordockProvider(),
)


def fetch_all(now: dt.datetime) -> list[Snapshot]:
    """Agrège les relevés des venues **dont la clé est configurée**, à l'instant ``now``.

    Key-gated : un provider sans toutes ses ``required_env`` est sauté (avertissement loggué),
    reproduisant le comportement historique. ``now`` est fourni explicitement (le registre ne
    possède pas l'horloge → pas d'ambiguïté point-in-time).

    Parameters
    ----------
    now
        Horodatage de relevé partagé par toutes les venues (UTC tz-aware).

    Returns
    -------
    list[core.ingestion.protocols.Snapshot]
        Les snapshots concaténés des venues actives (vide si aucune clé n'est présente).
    """
    out: list[Snapshot] = []
    for provider in PROVIDERS:
        missing = [key for key in provider.required_env if not os.environ.get(key)]
        if missing:
            logger.warning("%s absent : provider '%s' ignoré.", missing[0], provider.name)
            continue
        out.extend(provider.fetch(now))
    return out


__all__ = ["GpuPriceProvider", "PROVIDERS", "fetch_all"]
