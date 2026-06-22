"""Provider Prime Intellect : **agrégateur** multi-cloud de disponibilité GPU.

Prime Intellect expose les offres de **plusieurs providers sous-jacents** via un seul
endpoint (``/api/v1/availability``). La logique pure (``parse_primeintellect``) est isolée
de l'appel réseau (``fetch_primeintellect``, token-gated). Unité de sortie : USD par
GPU·heure (le prix d'offre ``prices.onDemand`` couvre ``gpuCount`` GPU → on divise).

Spécificité agrégateur : ``source`` est **qualifiée par le provider sous-jacent**
(``"primeintellect:<provider>"``) quand il est exposé, sinon ``"primeintellect"``. Cela
évite de masquer une venue déjà branchée en direct (dédup au niveau de l'indice par
``source``) — cf. handoff convergence (``CONVERGENCE.md``).
"""

from __future__ import annotations

import datetime as dt
import os
from typing import Any, Sequence

import requests

from core.ingestion.protocols import Snapshot
from core.ingestion.providers.base import normalize_gpu_model

_PRIMEINTELLECT_AVAILABILITY_URL = "https://api.primeintellect.ai/api/v1/availability"


def parse_primeintellect(
    items: Sequence[dict[str, Any]], snapshotted_at: dt.datetime
) -> list[Snapshot]:
    """Transforme les items d'availability Prime Intellect en snapshots $/GPU·h (pur).

    On retient les offres avec au moins un GPU (``gpuCount``) et un prix on-demand
    strictement positif ; le prix par GPU est ``prices.onDemand / gpuCount``. Le type de
    bail vient du drapeau ``isSpot``. La ``source`` est qualifiée par le provider
    sous-jacent quand il est connu.

    Champs descriptifs propagés quand exposés par l'API :
    - ``provider_detail`` : le fournisseur sous-jacent (ex. ``"datacrunch"``).
    - ``region`` : valeur brute (``region`` ou ``dataCenter``).
    - ``gpu_memory_gb`` : mémoire GPU en Go (``gpuMemory``).
    """
    out: list[Snapshot] = []
    for item in items:
        gpu_count = int(item.get("gpuCount", 0) or 0)
        if gpu_count <= 0:
            continue
        on_demand = item.get("prices", {}).get("onDemand")
        if not isinstance(on_demand, (int, float)) or on_demand <= 0:
            continue
        provider = item.get("provider")
        source = f"primeintellect:{provider}" if provider else "primeintellect"

        # Région : préférer ``dataCenter`` (plus précis) puis ``region``.
        region_raw = item.get("dataCenter") or item.get("region")
        region: str | None = str(region_raw) if region_raw else None

        # Mémoire GPU (Go).
        mem_raw = item.get("gpuMemory")
        gpu_memory_gb: float | None = float(mem_raw) if mem_raw is not None else None

        out.append(
            Snapshot(
                snapshotted_at=snapshotted_at,
                source=source,
                gpu_model=normalize_gpu_model(str(item.get("gpuType", ""))),
                price_usd_per_hour=float(on_demand) / gpu_count,
                lease_type="spot" if item.get("isSpot") else "on_demand",
                availability=gpu_count,
                region=region,
                gpu_memory_gb=gpu_memory_gb,
                provider_detail=str(provider) if provider else None,
            )
        )
    return out


def fetch_primeintellect(
    api_key: str, snapshotted_at: dt.datetime, *, timeout: float = 30.0
) -> list[Snapshot]:
    """Appel réel à l'API Prime Intellect → snapshots horodatés (I/O, non testé en unitaire)."""
    response = requests.get(
        _PRIMEINTELLECT_AVAILABILITY_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    # La réponse est un dict {gpu_type: [offres, ...]} → aplatir en une liste d'offres.
    items = [
        offer
        for offers in payload.values()
        if isinstance(offers, list)
        for offer in offers
        if isinstance(offer, dict)
    ]
    return parse_primeintellect(items, snapshotted_at)


class PrimeintellectProvider:
    """Provider Prime Intellect (token ``PRIMEINTELLECT_API_KEY``)."""

    name = "primeintellect"
    required_env: tuple[str, ...] = ("PRIMEINTELLECT_API_KEY",)

    def fetch(self, now: dt.datetime) -> list[Snapshot]:
        """Relève la disponibilité Prime Intellect (clé garantie par le registre key-gated)."""
        return fetch_primeintellect(os.environ["PRIMEINTELLECT_API_KEY"], now)
