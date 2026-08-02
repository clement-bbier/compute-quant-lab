"""TensorDock provider: marketplace host nodes (API v2, Bearer).

The pure logic (``parse_tensordock``) is isolated from the network call (``fetch_tensordock``,
token-gated). Authentication uses a Bearer token on ``TENSORDOCK_API_KEY``.

Chosen endpoint: ``GET https://dashboard.tensordock.com/api/v2/hostnodes``
- returns 403 without auth, **200 with a Bearer** (verified live 2026-06-23, reconfirmed
  in the V5.2 campaign): ``TENSORDOCK_API_KEY`` alone is sufficient, no other credential
  is sent or required.
- real envelope: ``{"data": {"hostnodes": [...]}}`` -- everything sits under ``data``; the
  ``_hostnodes_records`` helper reads ``data.hostnodes`` and tolerates the older flat form
  ``{"hostnodes": ...}`` as well as a mapping indexed by id.
- Warning: the live inventory has been **empty** on every check so far (2026-06-23 and
  the V5.2 campaign): ``{"data": {"hostnodes": []}}``. The per-node detail below (in
  particular the per-GPU vs per-node price hypothesis) is therefore still **unconfirmed**
  against a populated response -- there has never been a non-empty inventory to check it
  against.

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

Confirmed live (V5.2 campaign):

- Root envelope is ``{"data": {"hostnodes": [...]}}`` (a list, not a mapping indexed by id).
- The v2 endpoint ``/api/v2/hostnodes`` exists and returns 200 with a Bearer token.

Still **unconfirmed** (no populated live response seen to date):

- ``specs.gpu.price`` : is it really the $/GPU·h (the assumption taken here) or the price of
  the whole node (in which case it would need dividing by ``specs.gpu.amount``)?
- ``specs.gpu.amount`` : GPUs available for rent, or the machine total?
- ``specs.gpu.type`` : exact format of the GPU model name (e.g. ``"h100-sxm5-80gb"`` vs
  ``"H100 SXM5"``).

On an unexpected response / missing field, the connector cleanly returns ``[]``.
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Mapping, Sequence

import requests

from core.ingestion.protocols import Snapshot
from core.ingestion.providers.base import EnvKeyedProvider, normalize_gpu_model
from core.utils.coerce import opt_float
from core.utils.logging import get_logger, sanitize_for_log
from core.utils.net import DEFAULT_TIMEOUT_S, call_with_retry

logger = get_logger(__name__)

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
    api_key: str, snapshotted_at: dt.datetime, *, timeout: float = DEFAULT_TIMEOUT_S
) -> list[Snapshot]:
    """Real call to the TensorDock v2 API -> timestamped snapshots (I/O, not unit-tested).

    Retries on 5xx/timeout/connection error only (never on a 4xx). On any remaining
    network error / unexpected schema, cleanly returns ``[]`` but logs a WARNING first.
    """
    try:

        def _call() -> requests.Response:
            response = requests.get(
                _TENSORDOCK_HOSTNODES_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=timeout,
            )
            response.raise_for_status()
            return response

        payload = call_with_retry(_call, venue="tensordock").json()
    except Exception as exc:  # noqa: BLE001 -- one venue's failure must not sink the batch
        logger.warning(
            "tensordock: fetch failed after retries, returning no offers: %s",
            sanitize_for_log(str(exc)),
        )
        return []

    if not isinstance(payload, dict):
        logger.warning("tensordock: unexpected response schema (not a dict), returning no offers")
        return []
    return parse_tensordock(_hostnodes_records(payload), snapshotted_at)


class TensordockProvider(EnvKeyedProvider):
    """TensorDock provider (``TENSORDOCK_API_KEY`` token)."""

    name = "tensordock"
    required_env: tuple[str, ...] = ("TENSORDOCK_API_KEY",)
    _fetch_fn = staticmethod(fetch_tensordock)
