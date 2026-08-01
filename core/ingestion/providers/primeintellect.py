"""Prime Intellect provider: multi-cloud **aggregator** of GPU availability.

Prime Intellect exposes the offers of **several underlying providers** through a single
endpoint (``/api/v1/availability``). The pure logic (``parse_primeintellect``) is isolated
from the network call (``fetch_primeintellect``, token-gated). Output unit: USD per GPU-hour
(the ``prices.onDemand`` offer price covers ``gpuCount`` GPUs -> we divide).

Aggregator specificity: ``source`` is **qualified by the underlying provider**
(``"primeintellect:<provider>"``) when it is exposed, otherwise ``"primeintellect"``. This
avoids hiding a venue that is already wired in directly (index-level deduplication by
``source``) -- see ``docs/decisions/004-provider-registry-architecture.md``.
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
    """Transform Prime Intellect availability items into $/GPU·h snapshots (pure).

    We keep the offers with at least one GPU (``gpuCount``) and a strictly positive on-demand
    price; the per-GPU price is ``prices.onDemand / gpuCount``. The lease type comes from the
    ``isSpot`` flag. The ``source`` is qualified by the underlying provider when known.

    Descriptive fields propagated when exposed by the API:
    - ``provider_detail`` : the underlying provider (e.g. ``"datacrunch"``).
    - ``region`` : raw value (``region`` or ``dataCenter``).
    - ``gpu_memory_gb`` : GPU memory in GB (``gpuMemory``).
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

        # Region: prefer ``dataCenter`` (more precise) then ``region``.
        region_raw = item.get("dataCenter") or item.get("region")
        region: str | None = str(region_raw) if region_raw else None

        # GPU memory (GB).
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
    """Real call to the Prime Intellect API -> timestamped snapshots (I/O, not unit-tested)."""
    response = requests.get(
        _PRIMEINTELLECT_AVAILABILITY_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    # The response is a dict {gpu_type: [offers, ...]} -> flatten into a list of offers.
    items = [
        offer
        for offers in payload.values()
        if isinstance(offers, list)
        for offer in offers
        if isinstance(offer, dict)
    ]
    return parse_primeintellect(items, snapshotted_at)


class PrimeintellectProvider:
    """Prime Intellect provider (``PRIMEINTELLECT_API_KEY`` token)."""

    name = "primeintellect"
    required_env: tuple[str, ...] = ("PRIMEINTELLECT_API_KEY",)

    def fetch(self, now: dt.datetime) -> list[Snapshot]:
        """Read the Prime Intellect availability (key guaranteed by the key-gated registry)."""
        return fetch_primeintellect(os.environ["PRIMEINTELLECT_API_KEY"], now)
