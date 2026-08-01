"""I/O for exogenous variables (gas, HDD/CDD weather) + spread target (P01).

Real if an API token is present; otherwise a **deterministic synthetic
fallback** (fixed seed), logged — in the same manner as P01. The real weather/gas
connector falls to `data-engineer` (cf. CONVERGENCE: source registry CLAUDE.md §3).

The synthetic generative process deliberately injects a **lead**: energy
(and thus the spread) responds to gas and HDD *delayed* by ``LEAD_DAYS``. The
point-in-time pipeline must recover this lead — this is a demonstration of method, not
a claim of realism (cf. rule forward-real-simulated: everything is flagged SIMULATED).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from core.features import DEFAULT_PUBLICATION_LAGS, from_lagged_series
from core.features.protocols import ExogenousSource
from core.pricing import spark_spread_per_gpu_hour
from core.utils.config import get_env
from core.utils.logging import get_logger

logger = get_logger(__name__)

DEMO_SEED = 7
BALANCE_TEMP_C = 18.0  # reference temperature for HDD/CDD (deg C)
LEAD_DAYS = 3  # DGP lag: the exogenous variables lead energy by this many days
N_DAYS = 540  # ~18 months of daily data
WARMUP_DAYS = 60  # warmup (rolling windows) before the 1st decision instant


class SyntheticExogenousSource:
    """In-memory exogenous source (implements the `ExogenousSource` protocol)."""

    def __init__(self, frames: dict[str, pd.DataFrame]) -> None:
        self._frames = frames

    def names(self) -> list[str]:
        return list(self._frames)

    def vintages(self, name: str) -> pd.DataFrame:
        return self._frames[name]


@dataclass(frozen=True)
class ExogenousPanel:
    """Everything `run_signal` needs, already aligned."""

    source: ExogenousSource
    spread: pd.Series  # target (EUR/GPU-h), indexed by date
    raw: dict[str, pd.DataFrame]  # raw vintage frames (local cache data/raw/)
    decision_index: pd.DatetimeIndex
    mode: str  # "synthetic" | "real"


def _synthetic_drivers(
    rng: np.random.Generator, idx: pd.DatetimeIndex
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Seasonal, deterministic synthetic gas (EUR/MWh), HDD, CDD."""
    n = len(idx)
    t = np.arange(n)
    season = 10.0 * np.cos(2.0 * np.pi * t / 365.25)  # cold in winter
    temp = 12.0 + season + rng.normal(scale=2.0, size=n)
    hdd = np.clip(BALANCE_TEMP_C - temp, 0.0, None)
    cdd = np.clip(temp - BALANCE_TEMP_C, 0.0, None)
    gas = (
        30.0
        + 0.8 * hdd
        + 5.0 * np.cos(2.0 * np.pi * t / 365.25)
        + 0.1 * rng.normal(scale=3.0, size=n).cumsum()
    )
    gas = np.clip(gas, 5.0, None)
    return (
        pd.Series(gas, index=idx, name="gas_price"),
        pd.Series(hdd, index=idx, name="hdd"),
        pd.Series(cdd, index=idx, name="cdd"),
    )


def _spread_target(rng: np.random.Generator, gas: pd.Series, hdd: pd.Series) -> pd.Series:
    """Target spread (EUR/GPU-h) via `core.pricing`, driven by the delayed exogenous variables."""
    n = len(gas)
    # energy (EUR/MWh) = base + gas/HDD DELAYED by LEAD_DAYS + noise -> exogenous leads.
    energy = (
        40.0
        + 2.0 * gas.shift(LEAD_DAYS)
        + 0.6 * hdd.shift(LEAD_DAYS)
        + rng.normal(scale=1.5, size=n)
    ).bfill()
    # Compute deliberately *lightly* noised day-to-day: otherwise its noise drowns out the
    # energy leg (cost ~= 0.001275 EUR/GPU-h per EUR/MWh) and the exogenous lead becomes invisible.
    # Illustrative calibration (SIMULATED data) — not a claim of realism.
    compute = pd.Series(2.5 + rng.normal(scale=0.005, size=n), index=gas.index)
    return spark_spread_per_gpu_hour(compute, energy).rename("spread")


def _simulate_revision(values: pd.Series, lag: pd.Timedelta) -> pd.DataFrame:
    """Republishes a revised subset 1 month later (exercises the §6c path)."""
    sample = values.iloc[WARMUP_DAYS : WARMUP_DAYS + 30] * 1.05  # +5%, late revision
    return from_lagged_series(sample, lag + pd.Timedelta("30D"))


def load_panel(seed: int = DEMO_SEED) -> ExogenousPanel:
    """Loads the exogenous panel. Real if a token is present, otherwise deterministic synthetic."""
    token = get_env("EXOGENOUS_API_TOKEN")
    if token:
        logger.info(
            "Exogenous token present but the real connector is not wired up (cf. CONVERGENCE) "
            "-> falling back to synthetic."
        )
    mode = "synthetic"
    logger.info("Exogenous source: %s (seed=%d, injected lead=%d d).", mode, seed, LEAD_DAYS)

    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-09-01", periods=N_DAYS, freq="D", tz="UTC")
    gas, hdd, cdd = _synthetic_drivers(rng, idx)
    spread = _spread_target(rng, gas, hdd)

    lags = DEFAULT_PUBLICATION_LAGS
    frames = {
        "gas_price": pd.concat(
            [
                from_lagged_series(gas, lags["gas_price"]),
                _simulate_revision(gas, lags["gas_price"]),
            ],
            ignore_index=True,
        ),
        "hdd": from_lagged_series(hdd, lags["hdd"]),
        "cdd": from_lagged_series(cdd, lags["cdd"]),
    }
    decision_index = idx[WARMUP_DAYS : N_DAYS - 10]  # margin for the t+k target
    return ExogenousPanel(
        source=SyntheticExogenousSource(frames),
        spread=spread,
        raw=frames,
        decision_index=decision_index,
        mode=mode,
    )
