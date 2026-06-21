"""Connecteur marketplace GPU (données réelles, jambe compute du PoC).

Relève les prix de location *live* sur les marketplaces publiques (Vast.ai aujourd'hui,
RunPod en extension) et les normalise en :class:`~core.ingestion.protocols.Snapshot`.
La logique pure (parsing, normalisation des modèles) est isolée de l'appel réseau pour
être testable ; l'accès live est *token-gated* (clé via ``.env``), avec échec explicite
si aucune source n'est configurée.

Unité de sortie : USD par GPU·heure (le prix machine ``dph_total`` est divisé par le
nombre de GPU). Type de bail : on-demand.
"""

from __future__ import annotations

import datetime as dt
import logging
import os
import re
from typing import Any, Sequence

import requests

from core.ingestion.protocols import Snapshot

logger = logging.getLogger(__name__)

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

_VASTAI_OFFERS_URL = "https://console.vast.ai/api/v0/bundles/"


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


def parse_vastai_offers(offers: Sequence[dict[str, Any]], snapshotted_at: dt.datetime) -> list[Snapshot]:
    """Transforme des offres Vast.ai en snapshots $/GPU·h (logique pure, testable).

    On ne retient que les offres louables (``rentable``) avec au moins un GPU ; le prix
    par GPU est ``dph_total / num_gpus``.
    """
    out: list[Snapshot] = []
    for offer in offers:
        if not offer.get("rentable", False):
            continue
        num_gpus = int(offer.get("num_gpus", 0) or 0)
        if num_gpus <= 0:
            continue
        dph_total = float(offer.get("dph_total", 0.0))
        out.append(
            Snapshot(
                snapshotted_at=snapshotted_at,
                source="vastai",
                gpu_model=normalize_gpu_model(str(offer.get("gpu_name", ""))),
                price_usd_per_hour=dph_total / num_gpus,
                lease_type="on_demand",
                availability=num_gpus,
            )
        )
    return out


def fetch_vastai(api_key: str, snapshotted_at: dt.datetime, *, timeout: float = 30.0) -> list[Snapshot]:
    """Appel réel à l'API Vast.ai → snapshots horodatés (I/O, non testé en unitaire)."""
    response = requests.get(
        _VASTAI_OFFERS_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    return parse_vastai_offers(payload.get("offers", []), snapshotted_at)


def fetch_live_gpu_prices(now: dt.datetime | None = None) -> list[Snapshot]:
    """Relève le prix live de toutes les marketplaces configurées (par token ``.env``).

    Cible appelée par le collecteur planifié. Vast.ai est branché ; RunPod (GraphQL,
    ``RUNPOD_API_KEY``) est une extension documentée à ajouter ici.

    Raises
    ------
    RuntimeError
        Si aucune source n'est configurée (aucun token marketplace dans l'environnement).
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    snapshots: list[Snapshot] = []

    vastai_key = os.environ.get("VASTAI_API_KEY")
    if vastai_key:
        snapshots.extend(fetch_vastai(vastai_key, now))
    else:
        logger.warning("VASTAI_API_KEY absent : Vast.ai ignoré.")

    # Extension : RunPod (GraphQL) — brancher fetch_runpod(RUNPOD_API_KEY, now) ici.

    if not snapshots:
        raise RuntimeError(
            "Aucune source marketplace configurée : définir VASTAI_API_KEY (cf. .env / .env.example)."
        )
    return snapshots
