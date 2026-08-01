"""GPU marketplace connector -- **compatibility shim** (the logic lives in ``providers/``).

Vast.ai and RunPod were historically implemented here. To add venues in parallel without
collisions (*1 file = 1 venue*), the logic moved into the pluggable package
:mod:`core.ingestion.providers` (one module per venue + a protocol + a key-gated registry).
This module remains the **stable public API**:

- it **re-exports** the historical symbols (``normalize_gpu_model``, ``parse_*``,
  ``fetch_*``) so that no existing importer breaks (the ``core.ingestion`` facade, the P04
  tests);
- ``fetch_live_gpu_prices`` **delegates to the registry**
  :func:`core.ingestion.providers.fetch_all`, keeping its exact signature and behaviour (the
  scheduled collector ``infra/collectors/gpu_price_snapshot.py`` and the GitHub Actions live
  collection depend on it).

Output unit: USD per GPU-hour. Lease type: on-demand.
"""

from __future__ import annotations

import datetime as dt

from core.ingestion.protocols import Snapshot
from core.ingestion.providers import fetch_all
from core.ingestion.providers.base import normalize_gpu_model
from core.ingestion.providers.runpod import fetch_runpod, parse_runpod_gpu_types
from core.ingestion.providers.vastai import fetch_vastai, parse_vastai_offers


def fetch_live_gpu_prices(now: dt.datetime | None = None) -> list[Snapshot]:
    """Read the live price of every configured marketplace (gated by ``.env`` tokens).

    Entry point called by the scheduled collector. Delegates to the pluggable registry
    :func:`core.ingestion.providers.fetch_all` (key-gated: a venue without its key is
    skipped).

    Raises
    ------
    RuntimeError
        If no source is configured (no marketplace token in the environment).
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    snapshots = fetch_all(now)
    if not snapshots:
        raise RuntimeError(
            "No marketplace source is configured: set VASTAI_API_KEY or "
            "RUNPOD_API_KEY (see .env / .env.example)."
        )
    return snapshots


#: Historical symbols re-exported (backward compatibility: do not remove without convergence).
__all__ = [
    "normalize_gpu_model",
    "parse_vastai_offers",
    "fetch_vastai",
    "parse_runpod_gpu_types",
    "fetch_runpod",
    "fetch_live_gpu_prices",
]
