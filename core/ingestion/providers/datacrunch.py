"""Provider DataCrunch (alias Verda) : catalogue d'instances GPU (auth OAuth2).

La logique pure (``parse_datacrunch``) est isolée de l'appel réseau (``fetch_datacrunch``,
token-gated). DataCrunch cote au niveau **instance** (machine) : on divise
``price_per_hour`` par ``gpu.number_of_gpus`` pour obtenir le prix $/GPU·h. La venue
expose un prix **spot** (``spot_price_per_hour``) en plus de l'on-demand → on émet **deux**
``Snapshot`` (bails ``on_demand`` et ``spot``) quand le spot est disponible (> 0).
"""

from __future__ import annotations

import datetime as dt
import os
from typing import Any, Sequence

import requests

from core.ingestion.protocols import Snapshot
from core.ingestion.providers.base import normalize_gpu_model

_DATACRUNCH_TOKEN_URL = "https://api.datacrunch.io/v1/oauth2/token"
_DATACRUNCH_INSTANCE_TYPES_URL = "https://api.datacrunch.io/v1/instance-types"


def parse_datacrunch(
    instance_types: Sequence[dict[str, Any]], snapshotted_at: dt.datetime
) -> list[Snapshot]:
    """Transforme le catalogue ``/instance-types`` en snapshots $/GPU·h (logique pure).

    Pour chaque type d'instance avec au moins un GPU, on émet l'on-demand
    (``price_per_hour / number_of_gpus``) et, si ``spot_price_per_hour`` est positif, un
    second snapshot de bail ``spot``. Le modèle GPU est extrait de ``gpu.description``.

    Champs descriptifs propagés depuis les specs imbriquées :
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

        # Champs descriptifs (sous-structures optionnelles).
        gpu_mem_raw = (it.get("gpu_memory") or {}).get("size_in_gigabytes")
        gpu_memory_gb: float | None = float(gpu_mem_raw) if gpu_mem_raw is not None else None

        cpu_raw = (it.get("cpu") or {}).get("number_of_cores")
        vcpu: int | None = int(cpu_raw) if cpu_raw is not None else None

        ram_raw = (it.get("memory") or {}).get("size_in_gigabytes")
        ram_gb: float | None = float(ram_raw) if ram_raw is not None else None

        disk_raw = (it.get("storage") or {}).get("size_in_gigabytes")
        disk_gb: float | None = float(disk_raw) if disk_raw is not None else None

        # DataCrunch cote en chaînes ("2.19") et nomme le spot 'spot_price'.
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
                )
            )
    return out


def fetch_datacrunch(
    client_id: str,
    client_secret: str,
    snapshotted_at: dt.datetime,
    *,
    timeout: float = 30.0,
) -> list[Snapshot]:
    """OAuth2 (client_credentials) puis catalogue → snapshots horodatés (I/O, non testé)."""
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
    access_token = token_response.json()["access_token"]

    response = requests.get(
        _DATACRUNCH_INSTANCE_TYPES_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=timeout,
    )
    response.raise_for_status()
    return parse_datacrunch(response.json(), snapshotted_at)


class DatacrunchProvider:
    """Provider DataCrunch (paire ``DATACRUNCH_CLIENT_ID`` / ``DATACRUNCH_CLIENT_SECRET``)."""

    name = "datacrunch"
    required_env: tuple[str, ...] = ("DATACRUNCH_CLIENT_ID", "DATACRUNCH_CLIENT_SECRET")

    def fetch(self, now: dt.datetime) -> list[Snapshot]:
        """Relève le catalogue DataCrunch (clés garanties par le registre key-gated)."""
        return fetch_datacrunch(
            os.environ["DATACRUNCH_CLIENT_ID"], os.environ["DATACRUNCH_CLIENT_SECRET"], now
        )
