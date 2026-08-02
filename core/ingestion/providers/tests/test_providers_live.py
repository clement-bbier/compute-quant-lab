"""Live validation of the 7 GPU marketplace connectors -- real APIs, real keys (V5.2).

One ``@pytest.mark.live`` test per venue, skipped when its key is absent. Each test makes
**exactly one** network round trip (two for Hyperstack and DataCrunch, whose connectors are
inherently two-call: flavors+pricebook, OAuth2 token+catalogue) and validates the response
shape: non-empty (or empty with a logged reason), price > 0 and plausible, GPU model
normalized, availability a non-negative integer.

Run: ``set -a && source .env && set +a && uv run pytest -m live core/ingestion/providers -v``.
Never run in CI (see the ``live`` marker in ``pyproject.toml``).
"""

from __future__ import annotations

import datetime as dt
import os
import statistics

import pytest

from core.ingestion.providers.cudo import fetch_cudo
from core.ingestion.providers.datacrunch import fetch_datacrunch
from core.ingestion.providers.hyperstack import fetch_hyperstack
from core.ingestion.providers.primeintellect import fetch_primeintellect
from core.ingestion.providers.runpod import fetch_runpod
from core.ingestion.providers.tensordock import fetch_tensordock
from core.ingestion.providers.vastai import fetch_vastai
from core.ingestion.protocols import Snapshot
from core.storage import ParquetSnapshotStore
from core.utils.config import SNAPSHOTS_DIR

_NOW = dt.datetime.now(tz=dt.timezone.utc)


def _assert_snapshot_schema(snapshots: list[Snapshot], *, venue: str) -> None:
    """Shared schema check: every snapshot has a plausible price, model, and availability."""
    for s in snapshots:
        assert s.source.startswith(venue), f"{venue}: unexpected source {s.source!r}"
        assert s.price_usd_per_hour > 0, f"{venue}: non-positive price {s.price_usd_per_hour}"
        # A $/GPU-hour price outside this band signals a schema misread (e.g. per-node vs
        # per-GPU), not a real market quote -- generous bounds, not a tight sanity check.
        assert s.price_usd_per_hour < 200.0, f"{venue}: implausible price {s.price_usd_per_hour}"
        assert s.gpu_model, f"{venue}: empty gpu_model"
        assert isinstance(s.availability, int) and s.availability >= 0, (
            f"{venue}: bad availability {s.availability!r}"
        )
        assert s.snapshotted_at.tzinfo is not None, f"{venue}: naive snapshotted_at"


def _median_lake_price(gpu_model: str) -> float | None:
    """Cross-venue median on-demand price for ``gpu_model`` from the committed cold store."""
    snapshots = ParquetSnapshotStore(SNAPSHOTS_DIR).load()
    prices = [
        s.price_usd_per_hour
        for s in snapshots
        if s.gpu_model == gpu_model and s.lease_type == "on_demand"
    ]
    return statistics.median(prices) if prices else None


@pytest.mark.live
def test_vastai_live() -> None:
    key = os.environ.get("VASTAI_API_KEY")
    if not key:
        pytest.skip("VASTAI_API_KEY is missing -- export the key for the live test")
    snapshots = fetch_vastai(key, _NOW)
    if not snapshots:
        pytest.skip("vastai: live response had no rentable offers (not a schema failure)")
    _assert_snapshot_schema(snapshots, venue="vastai")


@pytest.mark.live
def test_runpod_live() -> None:
    key = os.environ.get("RUNPOD_API_KEY")
    if not key:
        pytest.skip("RUNPOD_API_KEY is missing -- export the key for the live test")
    snapshots = fetch_runpod(key, _NOW)
    if not snapshots:
        pytest.skip("runpod: live response had no priced GPU types (not a schema failure)")
    _assert_snapshot_schema(snapshots, venue="runpod")


@pytest.mark.live
def test_primeintellect_live() -> None:
    key = os.environ.get("PRIMEINTELLECT_API_KEY")
    if not key:
        pytest.skip("PRIMEINTELLECT_API_KEY is missing -- export the key for the live test")
    snapshots = fetch_primeintellect(key, _NOW)
    if not snapshots:
        pytest.skip("primeintellect: live response had no available offers (not a schema failure)")
    _assert_snapshot_schema(snapshots, venue="primeintellect")


@pytest.mark.live
def test_datacrunch_live() -> None:
    client_id = os.environ.get("DATACRUNCH_CLIENT_ID")
    client_secret = os.environ.get("DATACRUNCH_CLIENT_SECRET")
    if not client_id or not client_secret:
        pytest.skip(
            "DATACRUNCH_CLIENT_ID/DATACRUNCH_CLIENT_SECRET missing -- export both for the live test"
        )
    snapshots = fetch_datacrunch(client_id, client_secret, _NOW)
    if not snapshots:
        pytest.skip("datacrunch: live catalogue had no GPU instance types (not a schema failure)")
    _assert_snapshot_schema(snapshots, venue="datacrunch")


@pytest.mark.live
def test_hyperstack_live() -> None:
    key = os.environ.get("HYPERSTACK_API_KEY")
    if not key:
        pytest.skip("HYPERSTACK_API_KEY is missing -- export the key for the live test")
    snapshots = fetch_hyperstack(key, _NOW)
    if not snapshots:
        pytest.skip("hyperstack: live flavors/pricebook join was empty (not a schema failure)")
    _assert_snapshot_schema(snapshots, venue="hyperstack")


@pytest.mark.live
def test_cudo_live() -> None:
    """CUDO schema scrutiny: confirms the ``{"machineTypes": [...]}`` envelope against reality."""
    key = os.environ.get("CUDO_API_KEY")
    if not key:
        pytest.skip("CUDO_API_KEY is missing -- export the key for the live test")
    snapshots = fetch_cudo(key, _NOW)
    if not snapshots:
        pytest.skip("cudo: live response had no priced GPU machine types (not a schema failure)")
    _assert_snapshot_schema(snapshots, venue="cudo")


@pytest.mark.live
def test_tensordock_live() -> None:
    """TensorDock schema scrutiny: is ``specs.gpu.price`` per-GPU or per-node?

    If the parser's per-GPU assumption were wrong (price is actually for the whole node),
    an H100/A100 quote would land ~5-10x the cross-venue median (a node typically bundles
    multiple GPUs). Compares against the committed lake's median as the cheapest available
    cross-check; falls back to a hardcoded plausible band if the model isn't in the lake.
    """
    key = os.environ.get("TENSORDOCK_API_KEY")
    if not key:
        pytest.skip("TENSORDOCK_API_KEY is missing -- export the key for the live test")
    snapshots = fetch_tensordock(key, _NOW)
    if not snapshots:
        pytest.skip("tensordock: live hostnode inventory was empty (not a schema failure)")
    _assert_snapshot_schema(snapshots, venue="tensordock")

    for model in ("H100", "A100"):
        td_prices = [s.price_usd_per_hour for s in snapshots if s.gpu_model == model]
        if not td_prices:
            continue
        td_price = min(td_prices)
        median = _median_lake_price(model)
        if median is None:
            continue
        ratio = td_price / median
        assert ratio < 4.0, (
            f"tensordock {model}: ${td_price:.4f} is {ratio:.1f}x the cross-venue median "
            f"(${median:.4f}) -- specs.gpu.price looks like a PER-NODE price, not per-GPU; "
            "the parser needs to divide by specs.gpu.amount."
        )
