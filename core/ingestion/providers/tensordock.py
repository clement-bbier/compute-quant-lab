"""TensorDock provider: marketplace host nodes (API v2, Bearer).

The pure logic (``parse_tensordock``) is isolated from the network call (``fetch_tensordock``,
token-gated). Authentication uses a Bearer token on ``TENSORDOCK_API_KEY``.

Chosen endpoint: ``GET https://dashboard.tensordock.com/api/v2/hostnodes``
- returns 403 without auth, **200 with a Bearer** (verified live 2026-06-23)
- real envelope: ``{"data": {"hostnodes": [...]}}`` -- everything sits under ``data``; the
  ``_hostnodes_records`` helper reads ``data.hostnodes`` and tolerates the older flat form
  ``{"hostnodes": ...}`` as well as a mapping indexed by id.
- Warning: during the live test the inventory was **empty**
  (``{"data": {"hostnodes": []}}``): the per-node detail (below) is designed against the
  documented shape and still needs confirmation under load.

Expected per-node schema (to be confirmed live):

.. code-block:: json

    {
        "id": "hn-abc",
        "status": "online",
        "location": {"country": "US", "region": "us-east", "city": "NYC"},
        "specs": {
            "gpu": {"amount": 4, "type": "h100-sxm5-80gb", "vram": 80, "price": 2.80},
            "cpu": {"amount": 64, "price": 0.01},
            "ram": {"amount": 256, "price": 0.005},
            "storage": {"amount": 4000, "price": 0.0001}
        }
    }

Fields **to be confirmed live**:

- ``specs.gpu.price`` : is it really the $/GPU·h (the assumption taken here) or the price of
  the whole node (in which case it would need dividing by ``specs.gpu.amount``)?
- ``specs.gpu.amount`` : GPUs available for rent, or the machine total?
- ``specs.gpu.type`` : exact format of the GPU model name (e.g. ``"h100-sxm5-80gb"`` vs
  ``"H100 SXM5"``).
- Is the root envelope ``{"hostnodes": [...]}`` or ``{"hostnodes": {"id": {...}}}``?
- Is the v2 endpoint really ``/api/v2/hostnodes`` (403 without auth = it exists)?

On an unexpected response / missing field, the connector cleanly returns ``[]``.
"""

from __future__ import annotations

import datetime as dt
import os
from typing import Any, Mapping, Sequence

import requests

from core.ingestion.protocols import Snapshot
from core.ingestion.providers.base import normalize_gpu_model
from core.utils.coerce import opt_float

_TENSORDOCK_HOSTNODES_URL = "https://dashboard.tensordock.com/api/v2/hostnodes"


def _hostnodes_records(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Extract the node list from the ``{"data": {"hostnodes": ...}}`` envelope.

    Also tolerates the older flat form ``{"hostnodes": ...}`` (falling back to ``payload``)
    and ``hostnodes`` being either a list or a mapping indexed by id.
    """
    container = payload.get("data")
    if not isinstance(container, dict):
        container = payload
    hostnodes = container.get("hostnodes", [])
    if isinstance(hostnodes, dict):
        return list(hostnodes.values())
    if isinstance(hostnodes, list):
        return list(hostnodes)
    return []


def _node_to_snapshot(node: Any, snapshotted_at: dt.datetime) -> Snapshot | None:
    """Convert a TensorDock node into a ``Snapshot``, or ``None`` if malformed/unavailable.

    Keeps the nodes whose ``specs.gpu`` exposes a strictly positive available quantity
    (``amount``) and price. ``specs.gpu.price`` is assumed to be the $/GPU·h; the stock is
    ``specs.gpu.amount``. Region and memory come from ``location`` / ``specs.gpu.vram``.
    """
    if not isinstance(node, dict):
        return None
    specs = node.get("specs")
    gpu = specs.get("gpu") if isinstance(specs, dict) else None
    if not isinstance(gpu, dict):
        return None
    try:
        amount = int(gpu.get("amount") or 0)
    except (TypeError, ValueError):
        return None
    price = opt_float(gpu.get("price"))
    if amount <= 0 or price is None or price <= 0:
        return None
    location = node.get("location")
    if not isinstance(location, dict):
        location = {}
    return Snapshot(
        snapshotted_at=snapshotted_at,
        source="tensordock",
        gpu_model=normalize_gpu_model(str(gpu.get("type") or "")),
        price_usd_per_hour=price,
        lease_type="on_demand",
        availability=amount,
        region=location.get("region") or location.get("country"),
        gpu_memory_gb=opt_float(gpu.get("vram")),
    )


def parse_tensordock(
    hostnodes: Sequence[dict[str, Any]], snapshotted_at: dt.datetime
) -> list[Snapshot]:
    """Transform the TensorDock hostnodes into enriched $/GPU·h snapshots (pure logic).

    Parameters
    ----------
    hostnodes:
        List of nodes extracted from the API response (after ``_hostnodes_records``).
    snapshotted_at:
        UTC tz-aware timestamp of the observation.
    """
    snaps = (_node_to_snapshot(node, snapshotted_at) for node in hostnodes)
    return [s for s in snaps if s is not None]


def fetch_tensordock(
    api_key: str, snapshotted_at: dt.datetime, *, timeout: float = 30.0
) -> list[Snapshot]:
    """Real call to the TensorDock v2 API -> timestamped snapshots (I/O, not unit-tested).

    On a network error / unexpected schema, cleanly returns ``[]``.
    """
    try:
        response = requests.get(
            _TENSORDOCK_HOSTNODES_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return []

    if not isinstance(payload, dict):
        return []
    return parse_tensordock(_hostnodes_records(payload), snapshotted_at)


class TensordockProvider:
    """TensorDock provider (``TENSORDOCK_API_KEY`` token)."""

    name = "tensordock"
    required_env: tuple[str, ...] = ("TENSORDOCK_API_KEY",)

    def fetch(self, now: dt.datetime) -> list[Snapshot]:
        """Read the TensorDock hostnodes (key guaranteed by the key-gated registry)."""
        return fetch_tensordock(os.environ["TENSORDOCK_API_KEY"], now)
