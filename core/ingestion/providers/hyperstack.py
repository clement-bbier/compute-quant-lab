"""Provider Hyperstack (NexGen Cloud) : flavors GPU par région (header ``api_key``).

La logique pure (``parse_hyperstack``) est isolée de l'appel réseau (``fetch_hyperstack``,
token-gated). Deux appels sont nécessaires :

1. ``GET /v1/core/flavors`` → groupes de flavors par région / modèle GPU ; chaque
   ``FlavorFields`` porte ``{id, name, gpu, gpu_count, region_name, stock_available}``
   **sans prix**.
2. ``GET /v1/pricebook`` → liste plate ``[{name, value, original_value, ...}]`` où
   ``name`` est le nom du flavor (ex. ``"n3-H100x8"``) et ``value`` est le coût horaire
   **de la machine entière** (à diviser par ``gpu_count`` pour obtenir le $/GPU·h).

Jointure : ``FlavorFields.name`` ↔ ``PricebookEntry.name`` (sensible à la casse,
comme retourné par l'API).

Hypothèses **à confirmer en live à la convergence** :

- ``PricebookEntry.value`` est en USD/h pour la machine complète (÷ ``gpu_count`` → $/GPU·h).
  Alternative possible : prix déjà par GPU.
- ``PricebookEntry.name`` correspond exactement à ``FlavorFields.name`` (pas d'alias).
- ``FlavorFields.stock_available`` est un booléen (observé) ; l'API peut renvoyer un entier.
- L'endpoint ``/v1/pricebook`` est accessible sans scope supplémentaire (même clé que flavors).

⚠️ Si le join ne produit aucun prix (pricebook vide ou noms non concordants),
``parse_hyperstack`` renvoie ``[]`` proprement (aucune exception).
"""

from __future__ import annotations

import datetime as dt
import os
from typing import Any, Sequence

import requests

from core.ingestion.protocols import Snapshot
from core.ingestion.providers.base import normalize_gpu_model

_HYPERSTACK_BASE_URL = "https://infrahub-api.nexgencloud.com/v1"
_HYPERSTACK_FLAVORS_URL = f"{_HYPERSTACK_BASE_URL}/core/flavors"
_HYPERSTACK_PRICEBOOK_URL = f"{_HYPERSTACK_BASE_URL}/pricebook"


def _availability(stock: Any) -> int:
    """Normalise ``stock_available`` (booléen ou compteur) en profondeur de stock entière."""
    if isinstance(stock, bool):
        return 1 if stock else 0
    if isinstance(stock, (int, float)):
        return int(stock)
    return 0


def _build_price_index(pricebook: Sequence[dict[str, Any]]) -> dict[str, float]:
    """Construit un index ``{flavor_name: prix_machine_par_heure}`` depuis le pricebook.

    ``value`` est le prix horaire de la machine (USD/h) — non nul et positif requis.
    Les entrées sans ``name`` ou avec ``value`` invalide/nul sont ignorées.
    """
    index: dict[str, float] = {}
    for entry in pricebook:
        name = entry.get("name")
        value = entry.get("value")
        if not name or not isinstance(value, (int, float)) or value <= 0:
            continue
        index[str(name)] = float(value)
    return index


def parse_hyperstack(
    flavor_groups: Sequence[dict[str, Any]],
    pricebook: Sequence[dict[str, Any]],
    snapshotted_at: dt.datetime,
) -> list[Snapshot]:
    """Transforme les groupes de flavors Hyperstack + pricebook en snapshots $/GPU·h.

    Chaque groupe (par modèle/région) porte une liste ``flavors``. On retient les flavors
    avec au moins un GPU (``gpu_count``) dont le **nom est présent dans le pricebook** ; le
    prix par GPU est ``pricebook[flavor.name] / gpu_count``. Le modèle GPU vient du flavor
    (repli sur le groupe).

    Parameters
    ----------
    flavor_groups:
        Réponse de ``GET /v1/core/flavors`` → ``data`` (liste de groupes).
    pricebook:
        Réponse de ``GET /v1/pricebook`` (liste plate d'entrées tarifaires).
    snapshotted_at:
        Horodatage UTC tz-aware du relevé.
    """
    price_index = _build_price_index(pricebook)
    out: list[Snapshot] = []
    for group in flavor_groups:
        group_gpu = group.get("gpu")
        for flavor in group.get("flavors", []):
            gpu_count = int(flavor.get("gpu_count", 0) or 0)
            if gpu_count <= 0:
                continue
            flavor_name = flavor.get("name") or ""
            machine_price = price_index.get(flavor_name)
            if machine_price is None or machine_price <= 0:
                continue
            raw_model = flavor.get("gpu") or group_gpu or ""
            out.append(
                Snapshot(
                    snapshotted_at=snapshotted_at,
                    source="hyperstack",
                    gpu_model=normalize_gpu_model(str(raw_model)),
                    price_usd_per_hour=machine_price / gpu_count,
                    lease_type="on_demand",
                    availability=_availability(flavor.get("stock_available")),
                )
            )
    return out


def fetch_hyperstack(
    api_key: str, snapshotted_at: dt.datetime, *, timeout: float = 30.0
) -> list[Snapshot]:
    """Double appel à l'API Hyperstack (flavors + pricebook) → snapshots horodatés.

    Le prix vit dans le pricebook séparé ; les flavors ne portent que les specs.
    En cas de réponse inattendue (clé absente, JSON malformé), renvoie ``[]``.
    """
    headers = {"api_key": api_key}
    try:
        resp_flavors = requests.get(_HYPERSTACK_FLAVORS_URL, headers=headers, timeout=timeout)
        resp_flavors.raise_for_status()
        flavor_payload = resp_flavors.json()

        resp_pb = requests.get(_HYPERSTACK_PRICEBOOK_URL, headers=headers, timeout=timeout)
        resp_pb.raise_for_status()
        pricebook_payload = resp_pb.json()
    except Exception:
        return []

    flavor_groups: list[Any] = (
        flavor_payload.get("data", []) if isinstance(flavor_payload, dict) else []
    )
    flavor_groups = flavor_groups if isinstance(flavor_groups, list) else []
    # Le pricebook peut être une liste plate ou enveloppée dans {"data": [...]}
    raw_pb: Any
    if isinstance(pricebook_payload, list):
        pricebook: list[Any] = pricebook_payload
    elif isinstance(pricebook_payload, dict):
        raw_pb = pricebook_payload.get("data") or pricebook_payload.get("pricebook") or []
        pricebook = raw_pb if isinstance(raw_pb, list) else []
    else:
        pricebook = []

    return parse_hyperstack(flavor_groups, pricebook, snapshotted_at)


class HyperstackProvider:
    """Provider Hyperstack (token ``HYPERSTACK_API_KEY``)."""

    name = "hyperstack"
    required_env: tuple[str, ...] = ("HYPERSTACK_API_KEY",)

    def fetch(self, now: dt.datetime) -> list[Snapshot]:
        """Relève les flavors Hyperstack (clé garantie par le registre key-gated)."""
        return fetch_hyperstack(os.environ["HYPERSTACK_API_KEY"], now)
