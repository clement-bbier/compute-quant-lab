"""RunPod provider: on-demand prices per GPU type (GraphQL API).

The pure logic (``parse_runpod_gpu_types``) is isolated from the network call
(``fetch_runpod``, token-gated). RunPod already quotes per GPU; we keep the lowest available
on-demand price between secure and community cloud. Output unit: USD per GPU-hour. Lease
type: on-demand (the bid/spot ``minimumBidPrice`` is deliberately excluded).
"""

from __future__ import annotations

import datetime as dt
import os
from typing import Any, Sequence

import requests

from core.ingestion.protocols import Snapshot
from core.ingestion.providers.base import normalize_gpu_model

_RUNPOD_GRAPHQL_URL = "https://api.runpod.io/graphql"
#: On-demand price per GPU type (secure + community cloud). The bid/spot
#: (``minimumBidPrice``) is deliberately excluded: it is a different lease type.
_RUNPOD_QUERY = "{ gpuTypes { id displayName memoryInGb securePrice communityPrice } }"


def parse_runpod_gpu_types(
    gpu_types: Sequence[dict[str, Any]], snapshotted_at: dt.datetime
) -> list[Snapshot]:
    """Transform the RunPod ``gpuTypes`` response into $/GPU·h snapshots (pure logic).

    We keep the **lowest available on-demand price** between secure and community cloud
    (ignoring 0/``None`` = unavailable), which gives a representative price per model, robust
    to the ``(t, source, model)`` deduplication. The ``memoryInGb`` field is propagated into
    ``gpu_memory_gb`` when exposed.
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

        mem_raw = gpu.get("memoryInGb")
        gpu_memory_gb: float | None = float(mem_raw) if mem_raw is not None else None

        out.append(
            Snapshot(
                snapshotted_at=snapshotted_at,
                source="runpod",
                gpu_model=normalize_gpu_model(str(gpu.get("displayName", ""))),
                price_usd_per_hour=min(prices),
                lease_type="on_demand",
                availability=1,
                gpu_memory_gb=gpu_memory_gb,
            )
        )
    return out


def fetch_runpod(
    api_key: str, snapshotted_at: dt.datetime, *, timeout: float = 30.0
) -> list[Snapshot]:
    """Real call to the RunPod GraphQL API -> timestamped snapshots (I/O, not unit-tested)."""
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
    """RunPod provider (``RUNPOD_API_KEY`` token)."""

    name = "runpod"
    required_env: tuple[str, ...] = ("RUNPOD_API_KEY",)

    def fetch(self, now: dt.datetime) -> list[Snapshot]:
        """Read the RunPod prices (key guaranteed present by the key-gated registry)."""
        return fetch_runpod(os.environ["RUNPOD_API_KEY"], now)
