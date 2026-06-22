"""Provider Vast.ai : relevé des offres de location GPU (API bundles).

La logique pure (``parse_vastai_offers``) est isolée de l'appel réseau (``fetch_vastai``,
token-gated) pour être testable. Unité de sortie : USD par GPU·heure (le prix machine
``dph_total`` est divisé par le nombre de GPU). Type de bail : on-demand.
"""

from __future__ import annotations

import datetime as dt
import os
from typing import Any, Sequence

import requests

from core.ingestion.protocols import Snapshot
from core.ingestion.providers.base import normalize_gpu_model

_VASTAI_OFFERS_URL = "https://console.vast.ai/api/v0/bundles/"


def parse_vastai_offers(
    offers: Sequence[dict[str, Any]], snapshotted_at: dt.datetime
) -> list[Snapshot]:
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


def fetch_vastai(
    api_key: str, snapshotted_at: dt.datetime, *, timeout: float = 30.0
) -> list[Snapshot]:
    """Appel réel à l'API Vast.ai → snapshots horodatés (I/O, non testé en unitaire)."""
    response = requests.get(
        _VASTAI_OFFERS_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    return parse_vastai_offers(payload.get("offers", []), snapshotted_at)


class VastaiProvider:
    """Provider Vast.ai (token ``VASTAI_API_KEY``)."""

    name = "vastai"
    required_env: tuple[str, ...] = ("VASTAI_API_KEY",)

    def fetch(self, now: dt.datetime) -> list[Snapshot]:
        """Relève les offres Vast.ai (clé garantie présente par le registre key-gated)."""
        return fetch_vastai(os.environ["VASTAI_API_KEY"], now)
