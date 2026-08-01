"""Foundation of the ``energy`` subpackage: market protocol + key-gated registry.

Defines the :class:`EnergyMarket` injection abstraction (one connector = one energy market)
and the key-gated registry, **modelled on** ``core.ingestion.providers.base`` (the lab's
W1/W2 pattern). OCP principle: *adding a market means adding a file*, without touching the
core.

L0 point-in-time
----------------
The reserve forecast (:meth:`EnergyMarket.reserve_forecast`) must be timestamped at its
**publication time** (``publish_time`` column), never at the target time. This guarantees
that the calibration layer (P07) only consumes data known at the decision instant
(~18:00 CPT D-1 for ERCOT), with no look-ahead.

Key-gated registry
------------------
A market whose ``required_env`` is non-empty is listed in :func:`available_markets` only if
**all** of its keys are present in the environment. ERCOT is public
(``required_env = ()``), hence always listed.
"""

from __future__ import annotations

import os
from typing import Callable, Protocol, runtime_checkable

import pandas as pd

# ---------------------------------------------------------------------------
# Injectable protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class EnergyMarket(Protocol):
    """Price source of an energy market (injectable, key-gated).

    One connector = one market. The registry (:mod:`core.ingestion.energy`) exposes a market
    in :func:`available_markets` only if **all** of its ``required_env`` are present;
    otherwise it is silently hidden.

    Point-in-time contract (L0 section 2)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    :meth:`reserve_forecast` must include a ``publish_time`` column (UTC tz-aware)
    timestamped at the **publication** time of the ERCOT report, not at the target time.
    L0 calibration uses ``publish_time`` to filter causally (18:00 CPT D-1 cutoff).
    """

    #: Short market identifier (e.g. ``"ercot"``).
    name: str
    #: Required environment keys (registry gate). Empty = public.
    required_env: tuple[str, ...]

    def rtm_price(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series:
        """Real-time settlement price (RTM) over [start, end].

        Parameters
        ----------
        start, end
            Bounds of the time range (UTC tz-aware recommended; the connector handles the
            conversion from the market's local timezone).

        Returns
        -------
        pd.Series
            Series indexed by ``Interval Start`` (UTC tz-aware), values in $/MWh, sorted
            chronologically, with no injected NaN. Series name: ``"rtm_price_usd_mwh"``.
        """
        ...

    def reserve_forecast(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        """Reserve margin forecast published within the [start, end] range.

        Point-in-time: returns **every report published** between ``start`` and ``end``
        (publication range, not target range). The caller then filters on
        ``publish_time <= cutoff``.

        Returns
        -------
        pd.DataFrame
            Minimum columns:

            - ``publish_time``       : pd.Timestamp UTC -- report publication time.
            - ``interval_start``     : pd.Timestamp UTC -- target time of the interval.
            - ``interval_end``       : pd.Timestamp UTC -- end of the target interval.
            - ``forecast_load_mw``   : float -- forecast load (MW).
            - ``forecast_capacity_mw`` : float -- forecast available capacity (MW).
            - ``reserve_margin_mw``  : float -- margin = capacity - load (MW).

            Sorted by (``publish_time``, ``interval_start``).
        """
        ...


# ---------------------------------------------------------------------------
# Key-gated registry
# ---------------------------------------------------------------------------

#: Internal registry: key -> EnergyMarket instance.
_REGISTRY: dict[str, EnergyMarket] = {}


def register_market(key: str) -> Callable[[type], type]:
    """Decorator registering a market in the global registry.

    The registered market is reachable through :func:`get_market` and listed in
    :func:`available_markets` if its environment keys are present.

    Examples
    --------
    ::

        @register_market("ercot")
        class ErcotMarket:
            name = "ercot"
            required_env = ()
            ...
    """

    def _decorator(cls: type) -> type:
        _REGISTRY[key] = cls()
        return cls

    return _decorator


def get_market(key: str) -> EnergyMarket:
    """Retrieve a market instance by its key.

    Raises
    ------
    KeyError
        If the market is not registered.
    """
    if key not in _REGISTRY:
        raise KeyError(f"Market '{key}' is not registered. Known markets: {list(_REGISTRY)}")
    return _REGISTRY[key]


def available_markets() -> list[str]:
    """List the markets whose environment keys are all present.

    A market with ``required_env = ()`` is always listed (public).
    A key-gated market is hidden if any of its keys is missing from the shell.
    """
    result = []
    for key, market in _REGISTRY.items():
        if all(os.environ.get(env) for env in market.required_env):
            result.append(key)
    return result
