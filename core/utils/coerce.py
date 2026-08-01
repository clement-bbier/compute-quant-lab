"""Optional-value coercion helpers for untrusted external payloads.

Venue APIs and Parquet frames both hand back loosely typed values: a field may be
absent, ``null``, a string, or NaN. These helpers collapse all of those to ``None``
so the dataclasses in :mod:`core.ingestion.protocols` only ever see a valid value
or nothing at all.

Two families, deliberately kept distinct:

- :func:`opt_float` / :func:`opt_int` are **strict**: only real JSON numbers pass.
  Used by the provider parsers, where a string where a number belongs signals a
  schema drift we want to drop rather than silently reinterpret.
- :func:`lenient_float` / :func:`lenient_int` / :func:`lenient_str` additionally
  parse numeric strings and reject NaN. Used when reading back a DataFrame, where
  a missing optional column legitimately arrives as ``float('nan')``.
"""

from __future__ import annotations

import math
from typing import Any

__all__ = [
    "opt_float",
    "opt_int",
    "lenient_float",
    "lenient_int",
    "lenient_str",
]


def _is_real_number(value: Any) -> bool:
    """Whether ``value`` is a genuine int/float (``bool`` is not a number here)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def opt_float(value: Any) -> float | None:
    """Cast to float, or ``None`` when absent or not numeric (a bool is not a number)."""
    return float(value) if _is_real_number(value) else None


def opt_int(value: Any) -> int | None:
    """Cast to int, or ``None`` when absent or not numeric (a bool is not a number)."""
    return int(value) if _is_real_number(value) else None


def lenient_float(value: Any) -> float | None:
    """Cast to float, parsing numeric strings; ``None`` when unparseable or NaN."""
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(parsed) else parsed


def lenient_int(value: Any) -> int | None:
    """Cast to int via :func:`lenient_float`; ``None`` when unparseable or NaN."""
    parsed = lenient_float(value)
    return None if parsed is None else int(parsed)


def lenient_str(value: Any) -> str | None:
    """Cast to str; ``None`` when absent or a NaN float (missing Parquet column)."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return str(value)
