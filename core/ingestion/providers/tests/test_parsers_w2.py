"""Cas-or des 5 parsers W2 sur des payloads reprenant la forme réelle des API.

Chaque parser est **pur** : on l'appelle directement sur un échantillon (zéro réseau)
et on vérifie les ``Snapshot`` produits — unité $/GPU·h, type de bail (on-demand **et**
spot quand l'API l'expose), ``source``, normalisation du modèle et exclusion des offres
sans prix valide ou sans GPU. La forme exacte de certaines réponses (CUDO, Hyperstack,
TensorDock v2) reste à confirmer en live à la convergence ; ces tests figent le contrat
de parsing sur l'échantillon documenté.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from core.ingestion.providers import cudo, datacrunch, hyperstack, primeintellect, tensordock

_TS = dt.datetime(2026, 6, 21, tzinfo=dt.timezone.utc)


# ── Prime Intellect (agrégateur) ──────────────────────────────────────────────


def test_primeintellect_per_gpu_price_lease_and_source(
    primeintellect_items: list[dict[str, Any]],
) -> None:
    snaps = primeintellect.parse_primeintellect(primeintellect_items, _TS)

    assert len(snaps) == 3  # 0-GPU et prix invalide écartés
    by_id = {(s.source, s.gpu_model): s for s in snaps}

    h100 = by_id[("primeintellect:datacrunch", "H100")]
    assert h100.price_usd_per_hour == 3.0  # 24 / 8 GPU
    assert h100.lease_type == "on_demand"
    assert h100.availability == 8

    a100 = by_id[("primeintellect:runpod", "A100")]
    assert a100.price_usd_per_hour == 1.0  # 4 / 4 GPU
    assert a100.lease_type == "spot"  # isSpot=True

    rtx = by_id[("primeintellect", "RTX4090")]  # provider absent → source nue
    assert rtx.price_usd_per_hour == 0.5
    assert all(s.snapshotted_at == _TS for s in snaps)


# ── DataCrunch (on-demand + spot) ─────────────────────────────────────────────


def test_datacrunch_emits_on_demand_and_spot_per_gpu(
    datacrunch_instance_types: list[dict[str, Any]],
) -> None:
    snaps = datacrunch.parse_datacrunch(datacrunch_instance_types, _TS)

    assert len(snaps) == 3  # it-1 (on_demand+spot), it-2 (on_demand), it-3 (0 GPU) écartée
    by_key = {(s.gpu_model, s.lease_type): s.price_usd_per_hour for s in snaps}
    assert by_key[("H100", "on_demand")] == 3.0  # 24 / 8
    assert by_key[("H100", "spot")] == 1.5  # 12 / 8
    assert by_key[("A100", "on_demand")] == 1.20
    assert ("A100", "spot") not in by_key  # spot_price_per_hour = 0 → non émis
    assert all(s.source == "datacrunch" for s in snaps)


# ── CUDO (prix déjà par GPU, en chaîne) ───────────────────────────────────────


def test_cudo_uses_gpu_price_hr_value_as_per_gpu(
    cudo_machine_types: list[dict[str, Any]],
) -> None:
    snaps = cudo.parse_cudo(cudo_machine_types, _TS)

    assert len(snaps) == 2  # l'entrée sans modèle GPU / prix nul est écartée
    by_model = {s.gpu_model: s for s in snaps}
    assert by_model["H100"].price_usd_per_hour == 2.50  # gpuPriceHr.value (string) parsé
    assert by_model["H100"].availability == 16  # totalGpuFree
    assert by_model["A40"].price_usd_per_hour == 0.45
    assert all(s.source == "cudo" and s.lease_type == "on_demand" for s in snaps)


# ── Hyperstack (pricebook + flavors → join → par GPU) ────────────────────────


def test_hyperstack_joins_pricebook_and_divides_by_gpu_count(
    hyperstack_flavors: list[dict[str, Any]],
    hyperstack_pricebook: list[dict[str, Any]],
) -> None:
    snaps = hyperstack.parse_hyperstack(hyperstack_flavors, hyperstack_pricebook, _TS)

    # cpu-small (gpu_count=0) écarté ; 3 flavors GPU retenues
    assert len(snaps) == 3
    h100 = [s for s in snaps if s.gpu_model == "H100"]
    prices_h100 = {round(s.price_usd_per_hour, 4) for s in h100}
    assert prices_h100 == {round(27.92 / 8, 4), 3.49}  # 3.49 et 3.49
    l40 = next(s for s in snaps if s.gpu_model == "L40")
    assert l40.price_usd_per_hour == 1.00
    assert l40.availability == 0  # stock_available=False
    assert all(s.source == "hyperstack" for s in snaps)


def test_hyperstack_returns_empty_when_pricebook_empty(
    hyperstack_flavors: list[dict[str, Any]],
) -> None:
    # Pricebook vide → aucun prix connu → aucun snapshot émis
    snaps = hyperstack.parse_hyperstack(hyperstack_flavors, [], _TS)
    assert snaps == []


def test_hyperstack_returns_empty_when_flavor_name_missing_from_pricebook(
    hyperstack_flavors: list[dict[str, Any]],
) -> None:
    # Pricebook ne contient pas les noms des flavors → join vide
    pricebook_alien = [{"name": "other-flavor", "value": 99.0}]
    snaps = hyperstack.parse_hyperstack(hyperstack_flavors, pricebook_alien, _TS)
    assert snaps == []


# ── TensorDock v2 (specs.gpu.price = $/GPU·h) ─────────────────────────────────


def test_tensordock_parses_gpu_price_and_amount(
    tensordock_hostnodes: list[dict[str, Any]],
) -> None:
    snaps = tensordock.parse_tensordock(tensordock_hostnodes, _TS)

    assert len(snaps) == 2  # le nœud sans GPU dispo est écarté
    by_model = {s.gpu_model: s for s in snaps}
    assert by_model["H100"].price_usd_per_hour == 2.80
    assert by_model["H100"].availability == 4  # specs.gpu.amount
    assert by_model["RTX4090"].price_usd_per_hour == 0.45
    assert all(s.source == "tensordock" and s.lease_type == "on_demand" for s in snaps)


def test_tensordock_hostnodes_records_accepts_list_or_dict(
    tensordock_hostnodes: list[dict[str, Any]],
) -> None:
    # L'enveloppe v2 peut être une liste ou un mapping indexé par id : on tolère les deux.
    as_dict = {node["id"]: node for node in tensordock_hostnodes}
    assert (
        tensordock._hostnodes_records({"hostnodes": tensordock_hostnodes}) == tensordock_hostnodes
    )
    assert tensordock._hostnodes_records({"hostnodes": as_dict}) == list(as_dict.values())
    assert tensordock._hostnodes_records({}) == []
