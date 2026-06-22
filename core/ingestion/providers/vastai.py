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
    par GPU est ``dph_total / num_gpus``. Les champs descriptifs disponibles dans le
    payload (région, mémoire GPU, vCPU, RAM, disque) sont propagés quand présents.
    """
    out: list[Snapshot] = []
    for offer in offers:
        if not offer.get("rentable", False):
            continue
        num_gpus = int(offer.get("num_gpus", 0) or 0)
        if num_gpus <= 0:
            continue
        dph_total = float(offer.get("dph_total", 0.0))

        # Région : Vast.ai expose ``geolocation`` (ex. "US, GA") ou ``location``.
        region_raw = offer.get("geolocation") or offer.get("location")
        region: str | None = str(region_raw) if region_raw else None

        # Mémoire GPU : ``gpu_ram`` en Mo → Go.
        gpu_mem_mb = offer.get("gpu_ram")
        gpu_memory_gb: float | None = float(gpu_mem_mb) / 1024.0 if gpu_mem_mb else None

        # vCPU et RAM (Go).
        cpu_cores = offer.get("cpu_cores_effective") or offer.get("cpu_cores")
        vcpu: int | None = int(cpu_cores) if cpu_cores else None
        ram_raw = offer.get("cpu_ram")
        ram_gb: float | None = float(ram_raw) / 1024.0 if ram_raw else None

        # Disque (Go).
        disk_raw = offer.get("disk_space")
        disk_gb: float | None = float(disk_raw) if disk_raw else None

        out.append(
            Snapshot(
                snapshotted_at=snapshotted_at,
                source="vastai",
                gpu_model=normalize_gpu_model(str(offer.get("gpu_name", ""))),
                price_usd_per_hour=dph_total / num_gpus,
                lease_type="on_demand",
                availability=num_gpus,
                region=region,
                gpu_memory_gb=gpu_memory_gb,
                vcpu=vcpu,
                ram_gb=ram_gb,
                disk_gb=disk_gb,
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
