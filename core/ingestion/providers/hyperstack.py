"""Provider Hyperstack (NexGen Cloud) : flavors GPU par région (header ``api_key``).

La logique pure (``parse_hyperstack``) est isolée de l'appel réseau (``fetch_hyperstack``,
token-gated). On lit ``/v1/core/flavors`` (et non ``/v1/core/stocks`` qui ne porte pas le
prix) : un seul appel donne prix + région + stock. ``price_per_hour`` est le prix **du
flavor** (machine de ``gpu_count`` GPU) → on divise pour obtenir le $/GPU·h. Bail :
on-demand.

⚠️ À **confirmer en live à la convergence** : que ``price_per_hour`` est bien par flavor
(et non déjà par GPU), et la sémantique exacte de ``stock_available``.
"""

from __future__ import annotations

import datetime as dt
import os
from typing import Any, Sequence

import requests

from core.ingestion.protocols import Snapshot
from core.ingestion.providers.base import normalize_gpu_model

_HYPERSTACK_FLAVORS_URL = "https://infrahub-api.nexgencloud.com/v1/core/flavors"


def _availability(stock: Any) -> int:
    """Normalise ``stock_available`` (booléen ou compteur) en profondeur de stock entière."""
    if isinstance(stock, bool):
        return 1 if stock else 0
    if isinstance(stock, (int, float)):
        return int(stock)
    return 0


def parse_hyperstack(
    flavor_groups: Sequence[dict[str, Any]], snapshotted_at: dt.datetime
) -> list[Snapshot]:
    """Transforme les groupes de flavors Hyperstack en snapshots $/GPU·h (logique pure).

    Chaque groupe (par modèle/région) porte une liste ``flavors``. On retient les flavors
    avec au moins un GPU (``gpu_count``) et un ``price_per_hour`` positif ; le prix par GPU
    est ``price_per_hour / gpu_count``. Le modèle vient du flavor (repli sur le groupe).
    """
    out: list[Snapshot] = []
    for group in flavor_groups:
        group_gpu = group.get("gpu")
        for flavor in group.get("flavors", []):
            gpu_count = int(flavor.get("gpu_count", 0) or 0)
            price = flavor.get("price_per_hour")
            if gpu_count <= 0 or not isinstance(price, (int, float)) or price <= 0:
                continue
            raw_model = flavor.get("gpu") or group_gpu or ""
            out.append(
                Snapshot(
                    snapshotted_at=snapshotted_at,
                    source="hyperstack",
                    gpu_model=normalize_gpu_model(str(raw_model)),
                    price_usd_per_hour=float(price) / gpu_count,
                    lease_type="on_demand",
                    availability=_availability(flavor.get("stock_available")),
                )
            )
    return out


def fetch_hyperstack(
    api_key: str, snapshotted_at: dt.datetime, *, timeout: float = 30.0
) -> list[Snapshot]:
    """Appel réel à l'API Hyperstack → snapshots horodatés (I/O, non testé en unitaire)."""
    response = requests.get(
        _HYPERSTACK_FLAVORS_URL,
        headers={"api_key": api_key},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    return parse_hyperstack(payload.get("data", []), snapshotted_at)


class HyperstackProvider:
    """Provider Hyperstack (token ``HYPERSTACK_API_KEY``)."""

    name = "hyperstack"
    required_env: tuple[str, ...] = ("HYPERSTACK_API_KEY",)

    def fetch(self, now: dt.datetime) -> list[Snapshot]:
        """Relève les flavors Hyperstack (clé garantie par le registre key-gated)."""
        return fetch_hyperstack(os.environ["HYPERSTACK_API_KEY"], now)
