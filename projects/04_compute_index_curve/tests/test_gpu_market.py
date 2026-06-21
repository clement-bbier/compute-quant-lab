"""Tests de la logique pure du connecteur marketplace (parsing & normalisation).

Le parsing est séparé de l'appel réseau : on teste la transformation payload → Snapshot
sans dépendre d'une API live (l'appel HTTP token-gated reste non testé en unitaire).
"""

from __future__ import annotations

import datetime as dt

from core.ingestion.gpu_market import (
    normalize_gpu_model,
    parse_runpod_gpu_types,
    parse_vastai_offers,
)

_TS = dt.datetime(2026, 6, 21, tzinfo=dt.timezone.utc)


def test_normalize_gpu_model_extracts_family() -> None:
    assert normalize_gpu_model("H100 SXM") == "H100"
    assert normalize_gpu_model("NVIDIA A100-SXM4-80GB") == "A100"
    assert normalize_gpu_model("H200") == "H200"


def test_parse_vastai_offers_computes_per_gpu_price() -> None:
    offers = [
        {"gpu_name": "H100 SXM", "dph_total": 16.0, "num_gpus": 8, "rentable": True},
        {"gpu_name": "A100 PCIE", "dph_total": 4.0, "num_gpus": 4, "rentable": True},
        {"gpu_name": "H100 SXM", "dph_total": 2.0, "num_gpus": 1, "rentable": False},
    ]
    snaps = parse_vastai_offers(offers, _TS)

    by_model = {s.gpu_model: s.price_usd_per_hour for s in snaps}
    assert by_model["H100"] == 2.0  # 16 / 8 GPUs
    assert by_model["A100"] == 1.0  # 4 / 4 GPUs
    assert len(snaps) == 2  # l'offre non rentable est écartée
    assert all(s.source == "vastai" for s in snaps)
    assert all(s.lease_type == "on_demand" for s in snaps)
    assert all(s.snapshotted_at == _TS for s in snaps)


def test_parse_vastai_offers_skips_zero_gpu() -> None:
    offers = [{"gpu_name": "H100", "dph_total": 5.0, "num_gpus": 0, "rentable": True}]
    assert parse_vastai_offers(offers, _TS) == []


def test_parse_runpod_keeps_lowest_available_on_demand() -> None:
    # Forme réelle de l'API RunPod (gpuTypes) : secure + community cloud.
    gpu_types = [
        {"displayName": "A100 PCIe", "securePrice": 1.39, "communityPrice": 1.19},
        {"displayName": "A40", "securePrice": 0, "communityPrice": 0.35},
        {"displayName": "MI300X", "securePrice": None, "communityPrice": None},
    ]
    snaps = parse_runpod_gpu_types(gpu_types, _TS)

    by_model = {s.gpu_model: s.price_usd_per_hour for s in snaps}
    assert by_model["A100"] == 1.19  # min(secure, community)
    assert by_model["A40"] == 0.35  # securePrice=0 ignoré -> community retenu
    assert "MI300X" not in by_model  # aucun prix valide -> écarté
    assert all(s.source == "runpod" for s in snaps)
    assert all(s.lease_type == "on_demand" for s in snaps)
    assert len(snaps) == 2
