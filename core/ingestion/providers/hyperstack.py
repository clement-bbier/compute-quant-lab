"""Provider Hyperstack (NexGen Cloud) : prix GPU par région (header ``api_key``).

Logique pure (``parse_hyperstack``) isolée du réseau (``fetch_hyperstack``, token-gated).
Deux appels (validés en live 2026-06-23) :

1. ``GET /v1/core/flavors`` → groupes ``{gpu, region_name, flavors:[...]}`` ; chaque flavor
   porte ``{name, gpu, gpu_count, region_name, cpu, ram, disk, stock_available}`` **sans prix**.
2. ``GET /v1/pricebook`` → liste plate ``[{name, value, ...}]`` **par composant** : ``name``
   est le **type de GPU** (ex. ``"H100-80G-PCIe"``, ``"H100-80G-PCIe-spot"`` — et aussi
   ``"vCPU"``/``"RAM"``/modèles d'inférence, ignorés), ``value`` une **chaîne** donnant le
   prix **déjà par GPU et par heure** (ex. ``"1.9"``, ``"0E-9"``).

Jointure : ``flavor.gpu`` ↔ ``pricebook.name`` (et **non** ``flavor.name`` : le pricebook
n'est pas par-flavor). Le prix est déjà par GPU → **aucune** division par ``gpu_count``. Le
suffixe ``-spot`` du type distingue le bail et est retiré avant de normaliser le modèle
(sinon ``"L40-spot"`` → ``"L40S"``). ``value`` étant une chaîne, on la coerce et on écarte
les composants à prix nul (``"0E-9"``).

Si le join ne produit aucun prix (pricebook vide / noms non concordants), renvoie ``[]``.
"""

from __future__ import annotations

import datetime as dt
import os
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Sequence

import requests

from core.ingestion.protocols import Snapshot
from core.ingestion.providers.base import normalize_gpu_model

_HYPERSTACK_BASE_URL = "https://infrahub-api.nexgencloud.com/v1"
_HYPERSTACK_FLAVORS_URL = f"{_HYPERSTACK_BASE_URL}/core/flavors"
_HYPERSTACK_PRICEBOOK_URL = f"{_HYPERSTACK_BASE_URL}/pricebook"

#: Suffixe du type de GPU marquant une offre spot (ex. ``"H100-80G-PCIe-spot"``).
_SPOT_SUFFIX = "-spot"
#: Mémoire GPU encodée dans le type (ex. ``"H100-80G"`` → 80, ``"H200-141G"`` → 141).
_VRAM_RE = re.compile(r"(\d+)\s*G", re.IGNORECASE)


def _availability(stock: Any) -> int:
    """Normalise ``stock_available`` (booléen ou compteur) en profondeur de stock entière."""
    if isinstance(stock, bool):
        return 1 if stock else 0
    if isinstance(stock, (int, float)):
        return int(stock)
    return 0


def _coerce_price(value: Any) -> float | None:
    """Coerce une valeur de pricebook (souvent une chaîne, ``"1.9"`` / ``"0E-9"``) en USD/h > 0."""
    try:
        price = float(Decimal(str(value)))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return price if price > 0 else None


def _build_price_index(pricebook: Sequence[dict[str, Any]]) -> dict[str, float]:
    """Index ``{type_gpu: prix_par_gpu}`` du pricebook (valeurs en chaînes coercées, > 0 requis)."""
    index: dict[str, float] = {}
    for entry in pricebook:
        name = entry.get("name")
        price = _coerce_price(entry.get("value"))
        if name and price is not None:
            index[str(name)] = price
    return index


def _vram_gb(gpu_raw: str) -> float | None:
    """Extrait la mémoire GPU encodée dans le type (``"H100-80G-PCIe"`` → 80.0), sinon ``None``."""
    match = _VRAM_RE.search(gpu_raw)
    return float(match.group(1)) if match else None


def _opt_float(value: Any) -> float | None:
    """Cast optionnel en flottant (``None`` si absent ou non numérique ; un booléen n'est pas un nombre)."""
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _opt_int(value: Any) -> int | None:
    """Cast optionnel en entier (``None`` si absent ou non numérique)."""
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def parse_hyperstack(
    flavor_groups: Sequence[dict[str, Any]],
    pricebook: Sequence[dict[str, Any]],
    snapshotted_at: dt.datetime,
) -> list[Snapshot]:
    """Joint flavors ↔ pricebook (par ``flavor.gpu``) → snapshots $/GPU·h enrichis.

    On retient les flavors à ≥ 1 GPU dont le **type** ``gpu`` figure au pricebook. Le prix
    pricebook est **déjà par GPU** (pas de division). Le suffixe ``-spot`` fixe le bail et
    est retiré avant la normalisation du modèle. Champs descriptifs peuplés depuis le flavor
    (région, vCPU, RAM, disque) et le type (mémoire GPU).

    Parameters
    ----------
    flavor_groups:
        ``data`` de ``GET /v1/core/flavors`` (liste de groupes par type/région).
    pricebook:
        Liste plate de ``GET /v1/pricebook`` (entrées tarifaires par composant).
    snapshotted_at:
        Horodatage UTC tz-aware du relevé.
    """
    price_index = _build_price_index(pricebook)
    out: list[Snapshot] = []
    for group in flavor_groups:
        group_gpu = group.get("gpu")
        group_region = group.get("region_name")
        for flavor in group.get("flavors", []):
            if int(flavor.get("gpu_count", 0) or 0) <= 0:
                continue
            gpu_raw = str(flavor.get("gpu") or group_gpu or "")
            price = price_index.get(gpu_raw)
            if price is None:
                continue
            is_spot = gpu_raw.lower().endswith(_SPOT_SUFFIX)
            gpu_for_model = gpu_raw[: -len(_SPOT_SUFFIX)] if is_spot else gpu_raw
            out.append(
                Snapshot(
                    snapshotted_at=snapshotted_at,
                    source="hyperstack",
                    gpu_model=normalize_gpu_model(gpu_for_model),
                    price_usd_per_hour=price,
                    lease_type="spot" if is_spot else "on_demand",
                    availability=_availability(flavor.get("stock_available")),
                    region=flavor.get("region_name") or group_region,
                    gpu_memory_gb=_vram_gb(gpu_raw),
                    vcpu=_opt_int(flavor.get("cpu")),
                    ram_gb=_opt_float(flavor.get("ram")),
                    disk_gb=_opt_float(flavor.get("disk")),
                )
            )
    return out


def fetch_hyperstack(
    api_key: str, snapshotted_at: dt.datetime, *, timeout: float = 30.0
) -> list[Snapshot]:
    """Double appel à l'API Hyperstack (flavors + pricebook) → snapshots horodatés.

    Le prix vit dans le pricebook séparé ; les flavors ne portent que les specs. En cas de
    réponse inattendue (clé absente, JSON malformé, HTTP non-2xx), renvoie ``[]`` (jamais
    d'exception : le collecteur ne doit pas tomber pour une venue).
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

    flavor_groups = flavor_payload.get("data", []) if isinstance(flavor_payload, dict) else []
    flavor_groups = flavor_groups if isinstance(flavor_groups, list) else []
    # Le pricebook est une liste plate ; on tolère une enveloppe {"data": [...]} défensivement.
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
        """Relève les prix GPU Hyperstack (clé garantie par le registre key-gated)."""
        return fetch_hyperstack(os.environ["HYPERSTACK_API_KEY"], now)
