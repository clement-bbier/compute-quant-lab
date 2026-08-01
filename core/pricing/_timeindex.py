"""Backward-compatible alias of :mod:`core.utils.timeindex`.

The UTC index rule was promoted to ``core.utils`` so that ``core.pricing`` and
``core.features`` share a single tested implementation instead of two copies.
This module stays as a private import shim for the pricing package.
"""

from __future__ import annotations

from core.utils.timeindex import to_utc_index as to_utc_index  # re-export

__all__ = ["to_utc_index"]
