"""Provider CUDO Compute : types de machine VM avec prix par composant (Bearer).

La logique pure (``parse_cudo``) est isolée de l'appel réseau (``fetch_cudo``, token-gated).
CUDO **facture chaque composant séparément** : ``gpuPriceHr`` est donc **déjà** un prix
$/GPU·h (pas à diviser), exposé sous forme ``{"value": "2.50", "currency": "usd"}`` (valeur
en chaîne). On retient la disponibilité réseau ``totalGpuFree``. Bail : on-demand.

⚠️ Endpoint/forme à **confirmer en live à la convergence** (doc SPA non capturable hors
clé) : ``/v1/vms/machine-types`` (liste réseau-large) — variante per-data-center possible.
"""

from __future__ import annotations

import datetime as dt
import os
from typing import Any, Sequence

import requests

from core.ingestion.protocols import Snapshot
from core.ingestion.providers.base import normalize_gpu_model

_CUDO_MACHINE_TYPES_URL = "https://rest.compute.cudo.org/v1/vms/machine-types"


def _price_value(price_hr: Any) -> float | None:
    """Extrait la valeur numérique d'un ``{"value": "2.50", "currency": ...}`` CUDO.

    Tolère une valeur en chaîne ou numérique ; renvoie ``None`` si absente ou non
    convertible (l'entrée est alors écartée par l'appelant).
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
    """Transforme les types de machine CUDO en snapshots $/GPU·h (logique pure).

    On retient les machines équipées d'un GPU (``gpuModel`` non vide) avec un
    ``gpuPriceHr.value`` strictement positif. Ce prix est **directement** le $/GPU·h ;
    la disponibilité est ``totalGpuFree``.

    Champs descriptifs propagés :
    - ``region`` : ``dataCenterId`` (ex. ``"no-luster-1"``).
    - ``gpu_memory_gb`` : ``gpuMemoryGib`` (GiB → Go, ratio 1:1 en pratique).
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
            )
        )
    return out


def fetch_cudo(
    api_key: str, snapshotted_at: dt.datetime, *, timeout: float = 30.0
) -> list[Snapshot]:
    """Appel réel à l'API CUDO → snapshots horodatés (I/O, non testé en unitaire)."""
    response = requests.get(
        _CUDO_MACHINE_TYPES_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    return parse_cudo(payload.get("machineTypes", []), snapshotted_at)


class CudoProvider:
    """Provider CUDO Compute (token ``CUDO_API_KEY``)."""

    name = "cudo"
    required_env: tuple[str, ...] = ("CUDO_API_KEY",)

    def fetch(self, now: dt.datetime) -> list[Snapshot]:
        """Relève les types de machine CUDO (clé garantie par le registre key-gated)."""
        return fetch_cudo(os.environ["CUDO_API_KEY"], now)
