"""Provider TensorDock : nœuds hôtes du marketplace (API v2, Bearer).

La logique pure (``parse_tensordock``) est isolée de l'appel réseau (``fetch_tensordock``,
token-gated). L'authentification utilise un Bearer sur ``TENSORDOCK_API_KEY``.

Endpoint retenu : ``GET https://dashboard.tensordock.com/api/v2/hostnodes``
- retourne 403 sans auth, **200 avec Bearer** (vérifié en live 2026-06-23)
- enveloppe réelle : ``{"data": {"hostnodes": [...]}}`` — tout est sous ``data`` ; le helper
  ``_hostnodes_records`` lit ``data.hostnodes`` et tolère l'ancienne forme plate
  ``{"hostnodes": ...}`` ainsi qu'un mapping indexé par id.
- ⚠️ au test live l'inventaire était **vide** (``{"data": {"hostnodes": []}}``) : le détail
  par nœud (ci-dessous) est conçu sur la forme documentée et reste à confirmer en charge.

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
    """Extrait la liste des nœuds depuis l'enveloppe ``{"data": {"hostnodes": ...}}``.

    Tolère aussi l'ancienne forme plate ``{"hostnodes": ...}`` (repli sur ``payload``) et que
    ``hostnodes`` soit une liste ou un mapping indexé par id.
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


def _opt_float(value: Any) -> float | None:
    """Cast optionnel en flottant (``None`` si absent/non numérique ; un booléen n'est pas un nombre)."""
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _node_to_snapshot(node: Any, snapshotted_at: dt.datetime) -> Snapshot | None:
    """Convertit un nœud TensorDock en ``Snapshot``, ou ``None`` si non conforme/indisponible.

    Retient les nœuds dont ``specs.gpu`` expose une quantité dispo (``amount``) et un prix
    strictement positifs. ``specs.gpu.price`` est supposé être le $/GPU·h ; le stock est
    ``specs.gpu.amount``. Région et mémoire viennent de ``location`` / ``specs.gpu.vram``.
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
    price = _opt_float(gpu.get("price"))
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
        gpu_memory_gb=_opt_float(gpu.get("vram")),
    )


def parse_tensordock(
    hostnodes: Sequence[dict[str, Any]], snapshotted_at: dt.datetime
) -> list[Snapshot]:
    """Transforme les hostnodes TensorDock en snapshots $/GPU·h enrichis (logique pure).

    Parameters
    ----------
    hostnodes:
        Liste de nœuds extraite de la réponse API (après ``_hostnodes_records``).
    snapshotted_at:
        Horodatage UTC tz-aware du relevé.
    """
    snaps = (_node_to_snapshot(node, snapshotted_at) for node in hostnodes)
    return [s for s in snaps if s is not None]


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
