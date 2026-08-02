"""Pluggable registry of GPU marketplaces -- **1 file = 1 venue** (OCP).

Each venue (Vast.ai, RunPod, etc.) lives in its own module and exposes a class satisfying the
:class:`~core.ingestion.providers.base.GpuPriceProvider` protocol. The :data:`PROVIDERS`
registry lists them; :func:`fetch_all` only calls those whose ``required_env`` are **all**
present (key-gated), otherwise it logs a warning and skips.

Adding a venue -- **3 steps, without touching the core**:

1. Create ``core/ingestion/providers/<venue>.py``: ``parse_<venue>`` (pure) + ``fetch_<venue>``
   (network I/O, token-gated) + a ``<Venue>Provider`` class with ``name``, ``required_env``
   and ``fetch(now) -> list[Snapshot]`` (reuse ``base.normalize_gpu_model``).
2. Add ``<Venue>Provider()`` to the :data:`PROVIDERS` tuple below.
3. Write a parity test under ``tests/`` (parse -> expected ``Snapshot``) and add the key to
   the GitHub Secrets so the always-on collector can reach the venue.

No other layer changes: ``fetch_live_gpu_prices`` (the ``gpu_market`` shim) and the collector
automatically aggregate the new venue as soon as a key is configured.
"""

from __future__ import annotations

import datetime as dt
import os

from core.ingestion.protocols import Snapshot
from core.ingestion.providers.base import GpuPriceProvider
from core.ingestion.providers.cudo import CudoProvider
from core.ingestion.providers.datacrunch import DatacrunchProvider
from core.ingestion.providers.hyperstack import HyperstackProvider
from core.ingestion.providers.primeintellect import PrimeintellectProvider
from core.ingestion.providers.runpod import RunpodProvider
from core.ingestion.providers.tensordock import TensordockProvider
from core.ingestion.providers.vastai import VastaiProvider
from core.utils.logging import get_logger, sanitize_for_log

logger = get_logger(__name__)

#: Registered venues (7 active). The tuple order fixes the aggregation order of the
#: observations. Each one is key-gated in :func:`fetch_all`; a venue without its key is
#: simply skipped (a warning is logged).
PROVIDERS: tuple[GpuPriceProvider, ...] = (
    VastaiProvider(),
    RunpodProvider(),
    PrimeintellectProvider(),
    DatacrunchProvider(),
    CudoProvider(),
    HyperstackProvider(),
    TensordockProvider(),
)


def fetch_all(now: dt.datetime) -> list[Snapshot]:
    """Aggregate the observations of the venues **whose key is configured**, at ``now``.

    Key-gated: a provider missing any of its ``required_env`` is skipped (a warning is
    logged). ``now`` is supplied explicitly (the registry does not own the clock -> no
    point-in-time ambiguity).

    Parameters
    ----------
    now
        Observation timestamp shared by every venue (UTC tz-aware).

    Returns
    -------
    list[core.ingestion.protocols.Snapshot]
        The concatenated snapshots of the active venues (empty if no key is present).
    """
    out: list[Snapshot] = []
    for provider in PROVIDERS:
        missing = [key for key in provider.required_env if not os.environ.get(key)]
        if missing:
            logger.warning("%s is missing: provider '%s' skipped.", missing[0], provider.name)
            continue
        try:
            out.extend(provider.fetch(now))
        except Exception as exc:  # noqa: BLE001 -- one venue's HTTP failure must not sink the batch
            logger.warning(
                "provider '%s' fetch failed, skipped: %s",
                provider.name,
                sanitize_for_log(str(exc)),
            )
    return out


__all__ = ["GpuPriceProvider", "PROVIDERS", "fetch_all"]
