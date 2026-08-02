"""Hyperstack (NexGen Cloud) provider: GPU prices per region (``api_key`` header).

Pure logic (``parse_hyperstack``) isolated from the network (``fetch_hyperstack``,
token-gated). Two calls (validated live 2026-06-23):

1. ``GET /v1/core/flavors`` -> groups ``{gpu, region_name, flavors:[...]}``; each flavor
   carries ``{name, gpu, gpu_count, region_name, cpu, ram, disk, stock_available}`` **without
   a price**.
2. ``GET /v1/pricebook`` -> flat list ``[{name, value, ...}]`` **per component**: ``name`` is
   the **GPU type** (e.g. ``"H100-80G-PCIe"``, ``"H100-80G-PCIe-spot"`` -- and also
   ``"vCPU"``/``"RAM"``/inference models, which are ignored), ``value`` a **string** giving the
   price **already per GPU and per hour** (e.g. ``"1.9"``, ``"0E-9"``).

Join: ``flavor.gpu`` against ``pricebook.name`` (and **not** ``flavor.name``: the pricebook is
not per-flavor). The price is already per GPU -> **no** division by ``gpu_count``. The
``-spot`` suffix of the type distinguishes the lease and is stripped before normalising the
model (otherwise ``"L40-spot"`` -> ``"L40S"``). Since ``value`` is a string, we coerce it and
discard the zero-priced components (``"0E-9"``).

If the join yields no price (empty pricebook / non-matching names), returns ``[]``.
"""

from __future__ import annotations

import datetime as dt
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Sequence

import requests

from core.ingestion.protocols import Snapshot
from core.ingestion.providers.base import EnvKeyedProvider, normalize_gpu_model
from core.utils.coerce import opt_float, opt_int
from core.utils.logging import get_logger, sanitize_for_log
from core.utils.net import DEFAULT_TIMEOUT_S, call_with_retry

logger = get_logger(__name__)

_HYPERSTACK_BASE_URL = "https://infrahub-api.nexgencloud.com/v1"
_HYPERSTACK_FLAVORS_URL = f"{_HYPERSTACK_BASE_URL}/core/flavors"
_HYPERSTACK_PRICEBOOK_URL = f"{_HYPERSTACK_BASE_URL}/pricebook"

#: GPU type suffix marking a spot offer (e.g. ``"H100-80G-PCIe-spot"``).
_SPOT_SUFFIX = "-spot"
#: GPU memory encoded in the type (e.g. ``"H100-80G"`` -> 80, ``"H200-141G"`` -> 141).
_VRAM_RE = re.compile(r"(\d+)\s*G", re.IGNORECASE)


def _availability(stock: Any) -> int:
    """Normalise ``stock_available`` (boolean or counter) into an integer stock depth."""
    if isinstance(stock, bool):
        return 1 if stock else 0
    if isinstance(stock, (int, float)):
        return int(stock)
    return 0


def _coerce_price(value: Any) -> float | None:
    """Coerce a pricebook value (often a string, ``"1.9"`` / ``"0E-9"``) into USD/h > 0."""
    try:
        price = float(Decimal(str(value)))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return price if price > 0 else None


def _build_price_index(pricebook: Sequence[dict[str, Any]]) -> dict[str, float]:
    """Pricebook ``{gpu_type: price_per_gpu}`` index (string values coerced, > 0 required)."""
    index: dict[str, float] = {}
    for entry in pricebook:
        name = entry.get("name")
        price = _coerce_price(entry.get("value"))
        if name and price is not None:
            index[str(name)] = price
    return index


def _vram_gb(gpu_raw: str) -> float | None:
    """Extract the GPU memory encoded in the type (``"H100-80G-PCIe"`` -> 80.0), else ``None``."""
    match = _VRAM_RE.search(gpu_raw)
    return float(match.group(1)) if match else None


def parse_hyperstack(
    flavor_groups: Sequence[dict[str, Any]],
    pricebook: Sequence[dict[str, Any]],
    snapshotted_at: dt.datetime,
) -> list[Snapshot]:
    """Join flavors against the pricebook (on ``flavor.gpu``) -> enriched $/GPU·h snapshots.

    We keep the flavors with >= 1 GPU whose ``gpu`` **type** appears in the pricebook. The
    pricebook price is **already per GPU** (no division). The ``-spot`` suffix sets the lease
    and is stripped before the model normalisation. Descriptive fields are populated from the
    flavor (region, vCPU, RAM, disk) and from the type (GPU memory).

    Parameters
    ----------
    flavor_groups:
        ``data`` from ``GET /v1/core/flavors`` (list of groups per type/region).
    pricebook:
        Flat list from ``GET /v1/pricebook`` (pricing entries per component).
    snapshotted_at:
        UTC tz-aware timestamp of the observation.
    """
    price_index = _build_price_index(pricebook)
    out: list[Snapshot] = []
    for group in flavor_groups:
        group_gpu = group.get("gpu")
        group_region = group.get("region_name")
        for flavor in group.get("flavors", []):
            if int(flavor.get("gpu_count", 0) or 0) <= 0:
                continue
            gpu_raw = str(flavor.get("gpu") or group_gpu or "")
            price = price_index.get(gpu_raw)
            if price is None:
                continue
            is_spot = gpu_raw.lower().endswith(_SPOT_SUFFIX)
            gpu_for_model = gpu_raw[: -len(_SPOT_SUFFIX)] if is_spot else gpu_raw
            out.append(
                Snapshot(
                    snapshotted_at=snapshotted_at,
                    source="hyperstack",
                    gpu_model=normalize_gpu_model(gpu_for_model),
                    price_usd_per_hour=price,
                    lease_type="spot" if is_spot else "on_demand",
                    availability=_availability(flavor.get("stock_available")),
                    region=flavor.get("region_name") or group_region,
                    gpu_memory_gb=_vram_gb(gpu_raw),
                    vcpu=opt_int(flavor.get("cpu")),
                    ram_gb=opt_float(flavor.get("ram")),
                    disk_gb=opt_float(flavor.get("disk")),
                )
            )
    return out


def fetch_hyperstack(
    api_key: str, snapshotted_at: dt.datetime, *, timeout: float = DEFAULT_TIMEOUT_S
) -> list[Snapshot]:
    """Double call to the Hyperstack API (flavors + pricebook) -> timestamped snapshots.

    Each call retries on 5xx/timeout/connection error only (never on a 4xx). On any
    remaining unexpected failure (non-retryable HTTP error, malformed JSON), returns
    ``[]`` -- the collector must not go down because of one venue -- but logs a WARNING
    first: a silent ``[]`` is indistinguishable from "no offers" for the caller.
    """
    headers = {"api_key": api_key}
    try:

        def _fetch_flavors() -> requests.Response:
            resp = requests.get(_HYPERSTACK_FLAVORS_URL, headers=headers, timeout=timeout)
            resp.raise_for_status()
            return resp

        flavor_payload = call_with_retry(_fetch_flavors, venue="hyperstack").json()

        def _fetch_pricebook() -> requests.Response:
            resp = requests.get(_HYPERSTACK_PRICEBOOK_URL, headers=headers, timeout=timeout)
            resp.raise_for_status()
            return resp

        pricebook_payload = call_with_retry(_fetch_pricebook, venue="hyperstack").json()
    except Exception as exc:  # noqa: BLE001 -- one venue's failure must not sink the batch
        logger.warning(
            "hyperstack: fetch failed after retries, returning no offers: %s",
            sanitize_for_log(str(exc)),
        )
        return []

    flavor_groups = flavor_payload.get("data", []) if isinstance(flavor_payload, dict) else []
    flavor_groups = flavor_groups if isinstance(flavor_groups, list) else []
    # The pricebook is a flat list; we defensively tolerate a {"data": [...]} envelope.
    if isinstance(pricebook_payload, list):
        pricebook: list[Any] = pricebook_payload
    elif isinstance(pricebook_payload, dict):
        raw_pb = pricebook_payload.get("data") or pricebook_payload.get("pricebook") or []
        pricebook = raw_pb if isinstance(raw_pb, list) else []
    else:
        pricebook = []

    return parse_hyperstack(flavor_groups, pricebook, snapshotted_at)


class HyperstackProvider(EnvKeyedProvider):
    """Hyperstack provider (``HYPERSTACK_API_KEY`` token)."""

    name = "hyperstack"
    required_env: tuple[str, ...] = ("HYPERSTACK_API_KEY",)
    _fetch_fn = staticmethod(fetch_hyperstack)
