"""Foundation of the ``providers`` package: venue protocol + shared normalisation.

Defines the :class:`GpuPriceProvider` injection abstraction (one provider = one marketplace)
and the GPU model normalisation helper, **shared** by every venue. Placing it here -- rather
than in a venue file -- avoids any venue-to-venue coupling: each venue module depends only on
this foundation (OCP: *adding a venue means adding a file*, without touching the others).
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Protocol, runtime_checkable

from core.ingestion.protocols import Snapshot

#: Recognised datacenter GPU families (order = disambiguation priority).
_GPU_FAMILIES: tuple[str, ...] = (
    "B200",
    "H200",
    "H100",
    "A100",
    "L40S",
    "L40",
    "A6000",
    "A40",
    "V100",
    "RTX5090",
    "RTX4090",
)


def normalize_gpu_model(raw_name: str) -> str:
    """Extract the canonical family from a heterogeneous GPU name.

    ``"H100 SXM"`` -> ``"H100"``; ``"NVIDIA A100-SXM4-80GB"`` -> ``"A100"``. If no known
    family is found, returns the cleaned name (uppercase, alphanumeric).
    """
    compact = re.sub(r"[^A-Z0-9]", "", raw_name.upper())
    for family in _GPU_FAMILIES:
        if family in compact:
            return family
    return compact


@runtime_checkable
class GpuPriceProvider(Protocol):
    """Price source of a GPU marketplace (injectable, key-gated).

    One provider = one venue. The registry (:mod:`core.ingestion.providers`) calls ``fetch``
    only if **all** of the ``required_env`` are present in the environment; otherwise it logs
    a warning and skips the provider (historical behaviour).
    """

    #: Short venue identifier; equal to ``Snapshot.source`` (e.g. ``"vastai"``).
    name: str
    #: Required environment keys (``.env`` token) -- the registry gate.
    required_env: tuple[str, ...]

    def fetch(self, now: dt.datetime) -> list[Snapshot]:
        """Read the venue's live price at instant ``now`` (UTC tz-aware)."""
        ...
