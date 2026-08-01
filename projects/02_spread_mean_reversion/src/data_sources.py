"""Loading of energy<->compute spread data, point-in-time, with explicit provenance.

Three responsibilities, all wired to **real** data:

- ``load_energy_entsoe``: real ENTSO-E day-ahead prices (EUR/MWh), via ``entsoe-py`` (token-gated).
- ``compute_index_series``: $/GPU·h series for the compute spot index reconstructed from accumulated
  **real** marketplace snapshots (`core.ingestion.build_spot_index`, point-in-time, no carry-forward).
- ``build_spread``: assembles both legs via the P01 pricer (`core.pricing.SparkSpreadPricer`).

Every series carries a :class:`DataProvenance` whose ``simulated`` flag is **mandatory**
(rule ``forward-real-simulated``): simulated data is never served as if it were real.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Sequence

import pandas as pd

from core.ingestion import (
    DEFAULT_INDEX_CONFIG,
    IndexConfig,
    InsufficientDataError,
    Snapshot,
    build_spot_index,
)
from core.pricing import (
    ConstantFx,
    DataFramePriceSource,
    FxConverter,
    PowerModel,
    ServerPowerModel,
    SparkSpreadPricer,
    SpreadResult,
)

# Energy assumptions from the thesis: 8x H100 @ 700 W TDP, PUE 1.82 (≈ 10.2 kW per server).
_THESIS_TDP_W = 700.0
_THESIS_PUE = 1.82
_THESIS_N_GPUS = 8


@dataclass(frozen=True)
class DataProvenance:
    """Origin of a series, with a **non-optional** real/simulated boundary.

    Parameters
    ----------
    source : str
        Auditable label for the source (e.g. ``"entsoe+vastai"``, ``"synthetic_ou"``).
    simulated : bool
        ``True`` if the series comes from a model/simulation, ``False`` if it is real.
        No default value: declaring the origin is mandatory (rule ``forward-real-simulated``).
    units : str
        Unit of the series (default ``"EUR/GPU/h"``).
    """

    source: str
    simulated: bool
    units: str = "EUR/GPU/h"


@dataclass(frozen=True)
class SpreadDataset:
    """Spread to trade + P01 decomposition + provenance (real/simulated tracked)."""

    spread: pd.Series
    provenance: DataProvenance
    pricing: SpreadResult


def build_spread(
    energy: pd.DataFrame,
    compute: pd.DataFrame,
    *,
    gpu: str,
    region: str,
    provenance: DataProvenance,
    power_model: PowerModel | None = None,
    fx: FxConverter | None = None,
) -> SpreadDataset:
    """Prices the spark spread EUR/GPU·h via P01 from the two aligned legs.

    ``energy`` (EUR/MWh, columns = regions) and ``compute`` ($/GPU·h, columns = GPU) must be
    indexed UTC tz-aware. The pricer aligns compute onto the energy grid via a backward as-of
    join (anti look-ahead, guaranteed by P01).
    """
    pricer = SparkSpreadPricer(
        power_model
        or ServerPowerModel(tdp_w=_THESIS_TDP_W, pue=_THESIS_PUE, n_gpus=_THESIS_N_GPUS),
        fx or ConstantFx(rate=1.0),
    )
    result = pricer.price(DataFramePriceSource(energy, compute), gpu=gpu, region=region)
    return SpreadDataset(spread=result.spread, provenance=provenance, pricing=result)


def compute_index_series(
    snapshots: Sequence[Snapshot],
    grid: pd.DatetimeIndex,
    gpu: str,
    *,
    config: IndexConfig = DEFAULT_INDEX_CONFIG,
) -> pd.Series:
    """Time series of $/GPU·h for the compute spot index, **point-in-time** on ``grid``.

    Each point = ``build_spot_index(as_of)`` on the real snapshots (≤ as_of, no carry-forward).
    Instants with no fresh arrival are omitted (``InsufficientDataError``) rather than filled.
    """
    rows = list(snapshots)
    prices: dict[pd.Timestamp, float] = {}
    for as_of in grid:
        try:
            point = build_spot_index(rows, as_of.to_pydatetime(), gpu, config=config)
        except InsufficientDataError:
            continue
        prices[as_of] = point.price_usd_per_hour
    return pd.Series(prices, name=gpu, dtype=float)


def load_energy_entsoe(
    region: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    *,
    token: str | None = None,
) -> pd.Series:
    """**Real** ENTSO-E day-ahead prices (EUR/MWh, UTC index). Network call; token via ``ENTSOE_API_TOKEN``.

    Not unit-tested (I/O token-gated, like P04's marketplace connectors).

    Raises
    ------
    RuntimeError
        If no token is supplied and none is present in the environment.
    """
    from entsoe import EntsoePandasClient

    api_token = token or os.environ.get("ENTSOE_API_TOKEN")
    if not api_token:
        raise RuntimeError(
            "ENTSOE_API_TOKEN missing: real energy data unavailable (cf. .env.example)."
        )
    client = EntsoePandasClient(api_key=api_token)
    series = client.query_day_ahead_prices(region, start=start, end=end)
    series.index = series.index.tz_convert("UTC")
    return series.rename(region).astype(float)
