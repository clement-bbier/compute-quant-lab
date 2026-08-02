"""CUDO Compute provider: VM machine types with per-component pricing (Bearer).

The pure logic (``parse_cudo``) is isolated from the network call (``fetch_cudo``,
token-gated). CUDO **bills each component separately**: ``gpuPriceHr`` is therefore
**already** a $/GPU·h price (no division needed), exposed as
``{"value": "2.50", "currency": "usd"}`` (value as a string). We keep the network-wide
``totalGpuFree`` availability. Lease: on-demand.

Envelope and per-GPU pricing **confirmed against the live API**: ``GET
/v1/vms/machine-types`` returns ``{"machineTypes": [...]}``; ``gpuPriceHr.value`` lands
in the same range as the cross-venue median for the same model (e.g. A100 $1.50/GPU·h,
matching the committed lake's median exactly) -- the per-component, already-per-GPU
pricing assumption is correct, not a per-node price needing division.
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Sequence

import requests

from core.ingestion.protocols import Snapshot
from core.ingestion.providers.base import EnvKeyedProvider, normalize_gpu_model
from core.utils.net import DEFAULT_TIMEOUT_S, call_with_retry

_CUDO_MACHINE_TYPES_URL = "https://rest.compute.cudo.org/v1/vms/machine-types"


def _price_value(price_hr: Any) -> float | None:
    """Extract the numeric value from a CUDO ``{"value": "2.50", "currency": ...}``.

    Tolerates a string or numeric value; returns ``None`` if absent or not convertible (the
    entry is then discarded by the caller).
    """
    if not isinstance(price_hr, dict):
        return None
    value = price_hr.get("value")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_cudo(
    machine_types: Sequence[dict[str, Any]], snapshotted_at: dt.datetime
) -> list[Snapshot]:
    """Transform CUDO machine types into $/GPU·h snapshots (pure logic).

    We keep the machines equipped with a GPU (non-empty ``gpuModel``) whose
    ``gpuPriceHr.value`` is strictly positive. That price is **directly** the $/GPU·h; the
    availability is ``totalGpuFree``.

    Descriptive fields propagated:
    - ``region`` : ``dataCenterId`` (e.g. ``"no-luster-1"``).
    - ``gpu_memory_gb`` : ``gpuMemoryGib`` (GiB -> GB, 1:1 ratio in practice).
    """
    out: list[Snapshot] = []
    for mt in machine_types:
        gpu_model = str(mt.get("gpuModel", "") or "")
        price = _price_value(mt.get("gpuPriceHr"))
        if not gpu_model or price is None or price <= 0:
            continue

        dc_id = mt.get("dataCenterId")
        region: str | None = str(dc_id) if dc_id else None

        mem_gib = mt.get("gpuMemoryGib")
        gpu_memory_gb: float | None = float(mem_gib) if mem_gib is not None else None

        out.append(
            Snapshot(
                snapshotted_at=snapshotted_at,
                source="cudo",
                gpu_model=normalize_gpu_model(gpu_model),
                price_usd_per_hour=price,
                lease_type="on_demand",
                availability=int(mt.get("totalGpuFree", 0) or 0),
                region=region,
                gpu_memory_gb=gpu_memory_gb,
                simulated=False,
            )
        )
    return out


def fetch_cudo(
    api_key: str, snapshotted_at: dt.datetime, *, timeout: float = DEFAULT_TIMEOUT_S
) -> list[Snapshot]:
    """Real call to the CUDO API -> timestamped snapshots (I/O, not unit-tested).

    Retries on 5xx/timeout/connection error only (never on a 4xx).
    """

    def _call() -> requests.Response:
        response = requests.get(
            _CUDO_MACHINE_TYPES_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )
        response.raise_for_status()
        return response

    response = call_with_retry(_call, venue="cudo")
    payload = response.json()
    return parse_cudo(payload.get("machineTypes", []), snapshotted_at)


class CudoProvider(EnvKeyedProvider):
    """CUDO Compute provider (``CUDO_API_KEY`` token)."""

    name = "cudo"
    required_env: tuple[str, ...] = ("CUDO_API_KEY",)
    _fetch_fn = staticmethod(fetch_cudo)
