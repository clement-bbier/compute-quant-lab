"""Vast.ai provider: GPU rental offers (bundles API).

The pure logic (``parse_vastai_offers``) is isolated from the network call (``fetch_vastai``,
token-gated) to keep it testable. Output unit: USD per GPU-hour (the machine price
``dph_total`` is divided by the GPU count). Lease type: on-demand.
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
    """Transform Vast.ai offers into $/GPU·h snapshots (pure, testable logic).

    We only keep the rentable offers (``rentable``) with at least one GPU; the per-GPU price
    is ``dph_total / num_gpus``. The descriptive fields available in the payload (region, GPU
    memory, vCPU, RAM, disk) are propagated when present.
    """
    out: list[Snapshot] = []
    for offer in offers:
        if not offer.get("rentable", False):
            continue
        num_gpus = int(offer.get("num_gpus", 0) or 0)
        if num_gpus <= 0:
            continue
        dph_total = float(offer.get("dph_total", 0.0))

        # Region: Vast.ai exposes ``geolocation`` (e.g. "US, GA") or ``location``.
        region_raw = offer.get("geolocation") or offer.get("location")
        region: str | None = str(region_raw) if region_raw else None

        # GPU memory: ``gpu_ram`` in MB -> GB.
        gpu_mem_mb = offer.get("gpu_ram")
        gpu_memory_gb: float | None = float(gpu_mem_mb) / 1024.0 if gpu_mem_mb else None

        # vCPU and RAM (GB).
        cpu_cores = offer.get("cpu_cores_effective") or offer.get("cpu_cores")
        vcpu: int | None = int(cpu_cores) if cpu_cores else None
        ram_raw = offer.get("cpu_ram")
        ram_gb: float | None = float(ram_raw) / 1024.0 if ram_raw else None

        # Disk (GB).
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
    """Real call to the Vast.ai API -> timestamped snapshots (I/O, not unit-tested)."""
    response = requests.get(
        _VASTAI_OFFERS_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    return parse_vastai_offers(payload.get("offers", []), snapshotted_at)


class VastaiProvider:
    """Vast.ai provider (``VASTAI_API_KEY`` token)."""

    name = "vastai"
    required_env: tuple[str, ...] = ("VASTAI_API_KEY",)

    def fetch(self, now: dt.datetime) -> list[Snapshot]:
        """Read the Vast.ai offers (key guaranteed present by the key-gated registry)."""
        return fetch_vastai(os.environ["VASTAI_API_KEY"], now)
