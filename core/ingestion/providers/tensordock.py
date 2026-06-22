"""Provider TensorDock : nœuds hôtes du marketplace (API v2, Bearer).

La logique pure (``parse_tensordock``) est isolée de l'appel réseau (``fetch_tensordock``,
token-gated). L'authentification utilise un Bearer sur ``TENSORDOCK_API_KEY``.

Endpoint retenu : ``GET https://dashboard.tensordock.com/api/v2/hostnodes``
- retourne 403 sans auth (confirmé ; auth Bearer → 200 attendu)
- l'enveloppe ``hostnodes`` peut être une **liste** ou un **mapping indexé par id** ;
  le helper ``_hostnodes_records`` tolère les deux.

Schéma attendu par nœud (à confirmer en live) :

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

Champs **à confirmer en live** :

- ``specs.gpu.price`` : est-ce bien le $/GPU·h (hypothèse retenue) ou le prix du nœud
  entier (auquel cas il faudrait diviser par ``specs.gpu.amount``) ?
- ``specs.gpu.amount`` : GPU disponibles à la location ou total de la machine ?
- ``specs.gpu.type`` : format exact du nom du modèle GPU (ex. ``"h100-sxm5-80gb"`` vs
  ``"H100 SXM5"``).
- L'enveloppe racine est-elle ``{"hostnodes": [...]}`` ou ``{"hostnodes": {"id": {...}}}`` ?
- L'endpoint v2 est-il bien ``/api/v2/hostnodes`` (403 sans auth = existe) ?

En cas de réponse inattendue / champ absent, le connecteur renvoie ``[]`` proprement.
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
        return list(hostnodes)
    return []


def parse_tensordock(
    hostnodes: Sequence[dict[str, Any]], snapshotted_at: dt.datetime
) -> list[Snapshot]:
    """Transforme les hostnodes TensorDock en snapshots $/GPU·h (logique pure).

    On retient les nœuds dont ``specs.gpu`` expose une quantité disponible (``amount``)
    strictement positive et un prix positif. ``specs.gpu.price`` est supposé être le
    $/GPU·h ; la profondeur de stock est ``specs.gpu.amount``.

    Parameters
    ----------
    hostnodes:
        Liste de nœuds extraite de la réponse API (après ``_hostnodes_records``).
    snapshotted_at:
        Horodatage UTC tz-aware du relevé.
    """
    out: list[Snapshot] = []
    for node in hostnodes:
        if not isinstance(node, dict):
            continue
        specs = node.get("specs") or {}
        if not isinstance(specs, dict):
            continue
        gpu = specs.get("gpu") or {}
        if not isinstance(gpu, dict):
            continue
        amount = gpu.get("amount")
        try:
            amount = int(amount or 0)
        except (TypeError, ValueError):
            continue
        if amount <= 0:
            continue
        price = gpu.get("price")
        if not isinstance(price, (int, float)) or price <= 0:
            continue
        gpu_type = str(gpu.get("type") or "")
        out.append(
            Snapshot(
                snapshotted_at=snapshotted_at,
                source="tensordock",
                gpu_model=normalize_gpu_model(gpu_type),
                price_usd_per_hour=float(price),
                lease_type="on_demand",
                availability=amount,
            )
        )
    return out


def fetch_tensordock(
    api_key: str, snapshotted_at: dt.datetime, *, timeout: float = 30.0
) -> list[Snapshot]:
    """Appel réel à l'API TensorDock v2 → snapshots horodatés (I/O, non testé en unitaire).

    En cas d'erreur réseau / schéma inattendu, renvoie ``[]`` proprement.
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
    """Provider TensorDock (token ``TENSORDOCK_API_KEY``)."""

    name = "tensordock"
    required_env: tuple[str, ...] = ("TENSORDOCK_API_KEY",)

    def fetch(self, now: dt.datetime) -> list[Snapshot]:
        """Relève les hostnodes TensorDock (clé garantie par le registre key-gated)."""
        return fetch_tensordock(os.environ["TENSORDOCK_API_KEY"], now)
