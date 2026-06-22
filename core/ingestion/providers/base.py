"""Socle du paquet ``providers`` : protocole de venue + normalisation partagée.

Définit l'abstraction d'injection :class:`GpuPriceProvider` (un provider = une
marketplace) et l'helper de normalisation des modèles GPU, **partagé** par toutes les
venues. Le placer ici — plutôt que dans un fichier de venue — évite tout couplage
venue→venue : chaque module de venue ne dépend que de ce socle (OCP : *ajouter une venue
= ajouter un fichier*, sans toucher aux autres).
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Protocol, runtime_checkable

from core.ingestion.protocols import Snapshot

#: Familles de GPU datacenter reconnues (ordre = priorité de désambiguïsation).
_GPU_FAMILIES: tuple[str, ...] = (
    "B200",
    "H200",
    "H100",
    "A100",
    "L40S",
    "L40",
    "A6000",
    "A40",
    "V100",
    "RTX5090",
    "RTX4090",
)


def normalize_gpu_model(raw_name: str) -> str:
    """Extrait la famille canonique d'un nom de GPU hétérogène.

    ``"H100 SXM"`` → ``"H100"`` ; ``"NVIDIA A100-SXM4-80GB"`` → ``"A100"``. Si aucune
    famille connue n'est trouvée, renvoie le nom nettoyé (majuscules, alphanumérique).
    """
    compact = re.sub(r"[^A-Z0-9]", "", raw_name.upper())
    for family in _GPU_FAMILIES:
        if family in compact:
            return family
    return compact


@runtime_checkable
class GpuPriceProvider(Protocol):
    """Source de prix d'une marketplace GPU (injectable, key-gated).

    Un provider = une venue. Le registre (:mod:`core.ingestion.providers`) n'appelle
    ``fetch`` que si **toutes** les ``required_env`` sont présentes dans l'environnement ;
    sinon il loggue un avertissement et saute le provider (comportement historique).
    """

    #: Identifiant court de la venue ; égal à ``Snapshot.source`` (ex. ``"vastai"``).
    name: str
    #: Clés d'environnement nécessaires (token ``.env``) — gate du registre.
    required_env: tuple[str, ...]

    def fetch(self, now: dt.datetime) -> list[Snapshot]:
        """Relève le prix live de la venue à l'instant ``now`` (UTC tz-aware)."""
        ...
