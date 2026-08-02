"""DataCrunch provider (alias Verda): GPU instance catalogue (OAuth2 auth).

The pure logic (``parse_datacrunch``) is isolated from the network call
(``fetch_datacrunch``, token-gated). DataCrunch quotes at the **instance** (machine) level:
we divide ``price_per_hour`` by ``gpu.number_of_gpus`` to obtain the $/GPU·h price. The venue
exposes a **spot** price (``spot_price_per_hour``) in addition to on-demand -> we emit **two**
``Snapshot`` rows (``on_demand`` and ``spot`` leases) when spot is available (> 0).
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Sequence

import requests

from core.ingestion.protocols import Snapshot
from core.ingestion.providers.base import EnvKeyedProvider, normalize_gpu_model
from core.utils.net import DEFAULT_TIMEOUT_S, call_with_retry

_DATACRUNCH_TOKEN_URL = "https://api.datacrunch.io/v1/oauth2/token"
_DATACRUNCH_INSTANCE_TYPES_URL = "https://api.datacrunch.io/v1/instance-types"


def parse_datacrunch(
    instance_types: Sequence[dict[str, Any]], snapshotted_at: dt.datetime
) -> list[Snapshot]:
    """Transform the ``/instance-types`` catalogue into $/GPU·h snapshots (pure logic).

    For each instance type with at least one GPU, we emit the on-demand price
    (``price_per_hour / number_of_gpus``) and, if ``spot_price_per_hour`` is positive, a
    second snapshot with the ``spot`` lease. The GPU model is extracted from
    ``gpu.description``.

    Descriptive fields propagated from the nested specs:
    - ``gpu_memory_gb`` : ``gpu_memory.size_in_gigabytes``.
    - ``vcpu`` : ``cpu.number_of_cores``.
    - ``ram_gb`` : ``memory.size_in_gigabytes``.
    - ``disk_gb`` : ``storage.size_in_gigabytes``.
    """
    out: list[Snapshot] = []
    for it in instance_types:
        gpu = it.get("gpu") or {}
        n_gpus = int(gpu.get("number_of_gpus", 0) or 0)
        if n_gpus <= 0:
            continue
        model = normalize_gpu_model(str(gpu.get("description", "")))

        # Descriptive fields (optional sub-structures).
        gpu_mem_raw = (it.get("gpu_memory") or {}).get("size_in_gigabytes")
        gpu_memory_gb: float | None = float(gpu_mem_raw) if gpu_mem_raw is not None else None

        cpu_raw = (it.get("cpu") or {}).get("number_of_cores")
        vcpu: int | None = int(cpu_raw) if cpu_raw is not None else None

        ram_raw = (it.get("memory") or {}).get("size_in_gigabytes")
        ram_gb: float | None = float(ram_raw) if ram_raw is not None else None

        disk_raw = (it.get("storage") or {}).get("size_in_gigabytes")
        disk_gb: float | None = float(disk_raw) if disk_raw is not None else None

        # DataCrunch quotes as strings ("2.19") and names the spot field 'spot_price'.
        for lease_type, key in (("on_demand", "price_per_hour"), ("spot", "spot_price")):
            try:
                price = float(it.get(key))  # type: ignore[arg-type]
            except (TypeError, ValueError):
                continue
            if price <= 0:
                continue
            out.append(
                Snapshot(
                    snapshotted_at=snapshotted_at,
                    source="datacrunch",
                    gpu_model=model,
                    price_usd_per_hour=float(price) / n_gpus,
                    lease_type=lease_type,
                    availability=0,
                    gpu_memory_gb=gpu_memory_gb,
                    vcpu=vcpu,
                    ram_gb=ram_gb,
                    disk_gb=disk_gb,
                    simulated=False,
                )
            )
    return out


def fetch_datacrunch(
    client_id: str,
    client_secret: str,
    snapshotted_at: dt.datetime,
    *,
    timeout: float = DEFAULT_TIMEOUT_S,
) -> list[Snapshot]:
    """OAuth2 (client_credentials) then catalogue -> timestamped snapshots (I/O, untested).

    Each of the two calls (token, catalogue) retries independently on 5xx/timeout/
    connection error only (never on a 4xx).
    """

    def _token_call() -> requests.Response:
        token_response = requests.post(
            _DATACRUNCH_TOKEN_URL,
            json={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            timeout=timeout,
        )
        token_response.raise_for_status()
        return token_response

    token_response = call_with_retry(_token_call, venue="datacrunch")
    access_token = token_response.json()["access_token"]

    def _catalogue_call() -> requests.Response:
        response = requests.get(
            _DATACRUNCH_INSTANCE_TYPES_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=timeout,
        )
        response.raise_for_status()
        return response

    response = call_with_retry(_catalogue_call, venue="datacrunch")
    return parse_datacrunch(response.json(), snapshotted_at)


class DatacrunchProvider(EnvKeyedProvider):
    """DataCrunch provider (``DATACRUNCH_CLIENT_ID`` / ``DATACRUNCH_CLIENT_SECRET`` pair)."""

    name = "datacrunch"
    required_env: tuple[str, ...] = ("DATACRUNCH_CLIENT_ID", "DATACRUNCH_CLIENT_SECRET")
    _fetch_fn = staticmethod(fetch_datacrunch)
