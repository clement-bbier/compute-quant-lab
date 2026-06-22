"""Provider TensorDock : nœuds hôtes du marketplace (API v2, Bearer).

La logique pure (``parse_tensordock``) est isolée de l'appel réseau (``fetch_tensordock``,
token-gated). On lit ``/api/v2/hostnodes`` : chaque nœud porte ``specs.gpu`` avec un
modèle, une quantité **disponible** (``amount``) et un prix $/GPU·h (``price``). Bail :
on-demand. L'authentification est un Bearer sur ``TENSORDOCK_API_KEY`` (et **non** l'entête
``API_AUTHORIZATION`` de l'API v0).

⚠️ Forme v2 à **confirmer en live à la convergence** (doc Postman non capturable hors clé) :
l'enveloppe ``hostnodes`` peut être une **liste** ou un **mapping indexé par id** — le
helper ``_hostnodes_records`` tolère les deux ; l'emplacement exact du prix GPU est à figer.
"""

from __future__ import annotations

import datetime as dt
import os
from typing import Any, Mapping, Sequence

import requests

from core.ingestion.protocols import Snapshot
from core.ingestion.providers.base import normalize_gpu_model

_TENSORDOCK_HOSTNODES_URL = "https://dashboard.tensordock.com/api/v2/hostnodes"


def _hostnodes_records(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Extrait la liste des nœuds, que ``hostnodes`` soit une liste ou un mapping par id."""
    hostnodes = payload.get("hostnodes", [])
    if isinstance(hostnodes, dict):
        return list(hostnodes.values())
    if isinstance(hostnodes, list):
        return hostnodes
    return []


def parse_tensordock(
    hostnodes: Sequence[dict[str, Any]], snapshotted_at: dt.datetime
) -> list[Snapshot]:
    """Transforme les hostnodes TensorDock en snapshots $/GPU·h (logique pure).

    On retient les nœuds dont ``specs.gpu`` expose une quantité disponible (``amount``)
    strictement positive et un prix positif. ``price`` est **déjà** le $/GPU·h ; la
    profondeur de stock est ``amount``.
    """
    out: list[Snapshot] = []
    for node in hostnodes:
        gpu = (node.get("specs") or {}).get("gpu") or {}
        amount = int(gpu.get("amount", 0) or 0)
        price = gpu.get("price")
        if amount <= 0 or not isinstance(price, (int, float)) or price <= 0:
            continue
        out.append(
            Snapshot(
                snapshotted_at=snapshotted_at,
                source="tensordock",
                gpu_model=normalize_gpu_model(str(gpu.get("type", ""))),
                price_usd_per_hour=float(price),
                lease_type="on_demand",
                availability=amount,
            )
        )
    return out


def fetch_tensordock(
    api_key: str, snapshotted_at: dt.datetime, *, timeout: float = 30.0
) -> list[Snapshot]:
    """Appel réel à l'API TensorDock → snapshots horodatés (I/O, non testé en unitaire)."""
    response = requests.get(
        _TENSORDOCK_HOSTNODES_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=timeout,
    )
    response.raise_for_status()
    return parse_tensordock(_hostnodes_records(response.json()), snapshotted_at)


class TensordockProvider:
    """Provider TensorDock (token ``TENSORDOCK_API_KEY``)."""

    name = "tensordock"
    required_env: tuple[str, ...] = ("TENSORDOCK_API_KEY",)

    def fetch(self, now: dt.datetime) -> list[Snapshot]:
        """Relève les hostnodes TensorDock (clé garantie par le registre key-gated)."""
        return fetch_tensordock(os.environ["TENSORDOCK_API_KEY"], now)
