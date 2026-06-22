"""Provider RunPod : relevé des prix on-demand par type de GPU (API GraphQL).

La logique pure (``parse_runpod_gpu_types``) est isolée de l'appel réseau (``fetch_runpod``,
token-gated). RunPod cote déjà par GPU ; on retient le plus bas prix on-demand disponible
entre secure et community cloud. Unité de sortie : USD par GPU·heure. Type de bail :
on-demand (le bid/spot ``minimumBidPrice`` est volontairement exclu).
"""

from __future__ import annotations

import datetime as dt
import os
from typing import Any, Sequence

import requests

from core.ingestion.protocols import Snapshot
from core.ingestion.providers.base import normalize_gpu_model

_RUNPOD_GRAPHQL_URL = "https://api.runpod.io/graphql"
#: Prix on-demand par type de GPU (secure + community cloud). Le bid/spot
#: (``minimumBidPrice``) est volontairement exclu : autre type de bail.
_RUNPOD_QUERY = "{ gpuTypes { id displayName memoryInGb securePrice communityPrice } }"


def parse_runpod_gpu_types(
    gpu_types: Sequence[dict[str, Any]], snapshotted_at: dt.datetime
) -> list[Snapshot]:
    """Transforme la réponse RunPod ``gpuTypes`` en snapshots $/GPU·h (logique pure).

    On retient le **plus bas prix on-demand disponible** entre secure et community cloud
    (en ignorant 0/``None`` = indisponible), ce qui donne un prix représentatif par
    modèle, robuste à la dédup ``(t, source, modèle)``.
    """
    out: list[Snapshot] = []
    for gpu in gpu_types:
        prices = [
            float(p)
            for p in (gpu.get("securePrice"), gpu.get("communityPrice"))
            if isinstance(p, (int, float)) and p > 0
        ]
        if not prices:
            continue
        out.append(
            Snapshot(
                snapshotted_at=snapshotted_at,
                source="runpod",
                gpu_model=normalize_gpu_model(str(gpu.get("displayName", ""))),
                price_usd_per_hour=min(prices),
                lease_type="on_demand",
                availability=1,
            )
        )
    return out


def fetch_runpod(
    api_key: str, snapshotted_at: dt.datetime, *, timeout: float = 30.0
) -> list[Snapshot]:
    """Appel réel à l'API GraphQL RunPod → snapshots horodatés (I/O, non testé en unitaire)."""
    response = requests.post(
        _RUNPOD_GRAPHQL_URL,
        params={"api_key": api_key},
        json={"query": _RUNPOD_QUERY},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    gpu_types = (payload.get("data") or {}).get("gpuTypes") or []
    return parse_runpod_gpu_types(gpu_types, snapshotted_at)


class RunpodProvider:
    """Provider RunPod (token ``RUNPOD_API_KEY``)."""

    name = "runpod"
    required_env: tuple[str, ...] = ("RUNPOD_API_KEY",)

    def fetch(self, now: dt.datetime) -> list[Snapshot]:
        """Relève les prix RunPod (clé garantie présente par le registre key-gated)."""
        return fetch_runpod(os.environ["RUNPOD_API_KEY"], now)
