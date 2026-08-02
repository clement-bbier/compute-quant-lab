"""Parity: the ``gpu_market`` entry points produce EXACTLY the same ``Snapshot`` rows.

Two complementary guarantees:

1. **Object identity**: the ``core.ingestion.gpu_market`` shim re-exports the *same* functions
   as the ``providers`` package -- no implementation divergence is possible.
2. **Golden value cases**: the parsers match bit for bit the expectations of
   ``projects/04_compute_index_curve/tests/test_gpu_market.py``.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from core.ingestion import gpu_market
from core.ingestion.providers import base, runpod, vastai

_TS = dt.datetime(2026, 6, 21, tzinfo=dt.timezone.utc)


def test_shim_reexports_are_identical_objects() -> None:
    assert gpu_market.normalize_gpu_model is base.normalize_gpu_model
    assert gpu_market.parse_vastai_offers is vastai.parse_vastai_offers
    assert gpu_market.fetch_vastai is vastai.fetch_vastai
    assert gpu_market.parse_runpod_gpu_types is runpod.parse_runpod_gpu_types
    assert gpu_market.fetch_runpod is runpod.fetch_runpod


def test_normalize_gpu_model_extracts_family() -> None:
    assert base.normalize_gpu_model("H100 SXM") == "H100"
    assert base.normalize_gpu_model("NVIDIA A100-SXM4-80GB") == "A100"
    assert base.normalize_gpu_model("H200") == "H200"


def test_parse_vastai_offers_computes_per_gpu_price(vastai_offers: list[dict[str, Any]]) -> None:
    snaps = vastai.parse_vastai_offers(vastai_offers, _TS)

    by_model = {s.gpu_model: s.price_usd_per_hour for s in snaps}
    assert by_model["H100"] == 2.0  # 16 / 8 GPUs
    assert by_model["A100"] == 1.0  # 4 / 4 GPUs
    assert len(snaps) == 2  # the non-rentable offer is discarded
    assert all(s.source == "vastai" for s in snaps)
    assert all(s.lease_type == "on_demand" for s in snaps)
    assert all(s.snapshotted_at == _TS for s in snaps)


def test_parse_vastai_offers_skips_zero_gpu() -> None:
    offers = [{"gpu_name": "H100", "dph_total": 5.0, "num_gpus": 0, "rentable": True}]
    assert vastai.parse_vastai_offers(offers, _TS) == []


def test_parse_runpod_keeps_lowest_available_on_demand(
    runpod_gpu_types: list[dict[str, Any]],
) -> None:
    snaps = runpod.parse_runpod_gpu_types(runpod_gpu_types, _TS)

    by_model = {s.gpu_model: s.price_usd_per_hour for s in snaps}
    assert by_model["A100"] == 1.19  # min(secure, community)
    assert by_model["A40"] == 0.35  # securePrice=0 ignored -> community kept
    assert "MI300X" not in by_model  # no valid price -> discarded
    assert all(s.source == "runpod" for s in snaps)
    assert all(s.lease_type == "on_demand" for s in snaps)
    assert len(snaps) == 2
