"""Golden cases of the venue parsers on payloads reproducing the real API shapes.

Each parser is **pure**: we call it directly on a sample (zero network) and check the
``Snapshot`` rows produced -- $/GPU·h unit, lease type (on-demand **and** spot when the API
exposes it), ``source``, model normalisation and exclusion of the offers without a valid price
or without a GPU. The exact shape of some responses (CUDO, Hyperstack, TensorDock v2) is not
yet confirmed live; these tests freeze the parsing contract on the documented sample.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from core.ingestion.providers import cudo, datacrunch, hyperstack, primeintellect, tensordock

_TS = dt.datetime(2026, 6, 21, tzinfo=dt.timezone.utc)


# -- Prime Intellect (aggregator) ----------------------------------------------


def test_primeintellect_per_gpu_price_lease_and_source(
    primeintellect_items: list[dict[str, Any]],
) -> None:
    snaps = primeintellect.parse_primeintellect(primeintellect_items, _TS)

    assert len(snaps) == 3  # 0-GPU and invalid price discarded
    by_id = {(s.source, s.gpu_model): s for s in snaps}

    h100 = by_id[("primeintellect:datacrunch", "H100")]
    assert h100.price_usd_per_hour == 3.0  # 24 / 8 GPU
    assert h100.lease_type == "on_demand"
    assert h100.availability == 8

    a100 = by_id[("primeintellect:runpod", "A100")]
    assert a100.price_usd_per_hour == 1.0  # 4 / 4 GPU
    assert a100.lease_type == "spot"  # isSpot=True

    rtx = by_id[("primeintellect", "RTX4090")]  # provider missing -> bare source
    assert rtx.price_usd_per_hour == 0.5
    assert all(s.snapshotted_at == _TS for s in snaps)


# -- DataCrunch (on-demand + spot) ---------------------------------------------


def test_datacrunch_emits_on_demand_and_spot_per_gpu(
    datacrunch_instance_types: list[dict[str, Any]],
) -> None:
    snaps = datacrunch.parse_datacrunch(datacrunch_instance_types, _TS)

    assert len(snaps) == 3  # it-1 (on_demand+spot), it-2 (on_demand), it-3 (0 GPU) discarded
    by_key = {(s.gpu_model, s.lease_type): s.price_usd_per_hour for s in snaps}
    assert by_key[("H100", "on_demand")] == 3.0  # 24 / 8
    assert by_key[("H100", "spot")] == 1.5  # 12 / 8
    assert by_key[("A100", "on_demand")] == 1.20
    assert ("A100", "spot") not in by_key  # spot_price_per_hour = 0 -> not emitted
    assert all(s.source == "datacrunch" for s in snaps)


# -- CUDO (price already per GPU, as a string) ---------------------------------


def test_cudo_uses_gpu_price_hr_value_as_per_gpu(
    cudo_machine_types: list[dict[str, Any]],
) -> None:
    snaps = cudo.parse_cudo(cudo_machine_types, _TS)

    assert len(snaps) == 2  # the entry without a GPU model / zero price is discarded
    by_model = {s.gpu_model: s for s in snaps}
    assert by_model["H100"].price_usd_per_hour == 2.50  # gpuPriceHr.value (string) parsed
    assert by_model["H100"].availability == 16  # totalGpuFree
    assert by_model["A40"].price_usd_per_hour == 0.45
    assert all(s.source == "cudo" and s.lease_type == "on_demand" for s in snaps)


# -- Hyperstack (per-component pricebook + flavors -> join on GPU type -> per GPU) --


def test_hyperstack_joins_pricebook_on_gpu_type_per_gpu(
    hyperstack_flavors: list[dict[str, Any]],
    hyperstack_pricebook: list[dict[str, Any]],
) -> None:
    snaps = hyperstack.parse_hyperstack(hyperstack_flavors, hyperstack_pricebook, _TS)

    # 2 H100 on_demand + 1 H100 spot + 1 L40; cpu-small and A100 (not in pricebook) discarded
    assert len(snaps) == 4
    h100 = [s for s in snaps if s.gpu_model == "H100"]
    # price ALREADY per GPU (never /8): on_demand 1.9, spot 1.52
    assert {s.price_usd_per_hour for s in h100} == {1.9, 1.52}
    l40 = next(s for s in snaps if s.gpu_model == "L40")
    assert l40.price_usd_per_hour == 0.99
    assert l40.availability == 0  # stock_available=False
    assert all(s.source == "hyperstack" for s in snaps)


def test_hyperstack_returns_empty_when_pricebook_empty(
    hyperstack_flavors: list[dict[str, Any]],
) -> None:
    # Empty pricebook -> no known price -> no snapshot emitted
    snaps = hyperstack.parse_hyperstack(hyperstack_flavors, [], _TS)
    assert snaps == []


def test_hyperstack_returns_empty_when_gpu_type_missing_from_pricebook(
    hyperstack_flavors: list[dict[str, Any]],
) -> None:
    # The pricebook contains none of the flavors' GPU types -> empty join
    pricebook_alien = [{"name": "other-gpu", "value": "99.0"}]
    snaps = hyperstack.parse_hyperstack(hyperstack_flavors, pricebook_alien, _TS)
    assert snaps == []


# -- TensorDock v2 (specs.gpu.price = $/GPU·h) ---------------------------------


def test_tensordock_parses_gpu_price_and_amount(
    tensordock_hostnodes: list[dict[str, Any]],
) -> None:
    snaps = tensordock.parse_tensordock(tensordock_hostnodes, _TS)

    assert len(snaps) == 2  # the node without an available GPU is discarded
    by_model = {s.gpu_model: s for s in snaps}
    assert by_model["H100"].price_usd_per_hour == 2.80
    assert by_model["H100"].availability == 4  # specs.gpu.amount
    assert by_model["RTX4090"].price_usd_per_hour == 0.45
    assert all(s.source == "tensordock" and s.lease_type == "on_demand" for s in snaps)


def test_tensordock_hostnodes_records_accepts_list_or_dict(
    tensordock_hostnodes: list[dict[str, Any]],
) -> None:
    # The v2 envelope can be a list or a mapping indexed by id: we tolerate both.
    as_dict = {node["id"]: node for node in tensordock_hostnodes}
    assert (
        tensordock._hostnodes_records({"hostnodes": tensordock_hostnodes}) == tensordock_hostnodes
    )
    assert tensordock._hostnodes_records({"hostnodes": as_dict}) == list(as_dict.values())
    assert tensordock._hostnodes_records({}) == []
