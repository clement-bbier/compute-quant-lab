"""Builds the aligned energy/compute dataset for the P01 pricer.

**Energy** leg: ENTSO-E spot price (FR day-ahead, EUR/MWh, UTC) if a token is
available and `entsoe-py` is installed; otherwise **deterministic synthetic
fallback** (clearly logged) so the pipeline stays reproducible offline.

**Compute** leg: realistic Silicon Data *stub* (H100, $/GPU·h) until access
is confirmed — swapping to the real feed is trivial (one function).

Output: ``data/interim/aligned_spark.parquet`` (hourly UTC grid, co-timestamped,
lag=0), versioned as plain git. No writes to ``data/raw/`` (immutable).
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd

from core.utils.logging import configure_logging, get_logger, sanitize_for_log

log = get_logger("prepare_dataset")

# Repo root: this file lives at projects/01_digital_spark_spread/src/.
REPO_ROOT = Path(__file__).resolve().parents[3]
OUTPUT = REPO_ROOT / "data" / "interim" / "aligned_spark.parquet"

REGION = "FR"
WINDOW_START = "2025-01-01"
WINDOW_END = "2025-02-01"  # exclusive: one month of hourly data
ENERGY_COL = "energy_eur_per_mwh"
COMPUTE_COL = "compute_usd_per_gpu_h"


def _hourly_index(start: str, end: str) -> pd.DatetimeIndex:
    """Hourly UTC tz-aware grid, right edge excluded."""
    return pd.date_range(start, end, freq="h", tz="UTC", inclusive="left")


def fetch_energy_entsoe(index: pd.DatetimeIndex, region: str) -> pd.Series | None:
    """Attempts to fetch the real ENTSO-E day-ahead price. None if unavailable."""
    token = os.environ.get("ENTSOE_API_TOKEN") or os.environ.get("ENTSOE_API_KEY")
    if not token:
        log.warning("No ENTSO-E token (ENTSOE_API_TOKEN) — synthetic fallback.")
        return None
    try:
        from entsoe import EntsoePandasClient
    except ImportError:
        log.warning("entsoe-py not installed — synthetic fallback.")
        return None
    try:
        client = EntsoePandasClient(api_key=token)
        start = pd.Timestamp(WINDOW_START, tz="UTC")
        end = pd.Timestamp(WINDOW_END, tz="UTC")
        raw = client.query_day_ahead_prices(region, start=start, end=end)
        series = raw.tz_convert("UTC").reindex(index).ffill()
        log.info("Real ENTSO-E data fetched: %d points (%s).", series.notna().sum(), region)
        return series.astype(float)
    except Exception as exc:  # noqa: BLE001 - documented robust fallback
        log.warning("ENTSO-E fetch failed (%s) — synthetic fallback.", sanitize_for_log(str(exc)))
        return None


def synthetic_energy(index: pd.DatetimeIndex, *, seed: int = 7) -> pd.Series:
    """Deterministic fallback: daily seasonality + noise (EUR/MWh, >= 0)."""
    rng = np.random.default_rng(seed)
    hours = index.hour.to_numpy()
    daily = 90.0 + 35.0 * np.sin((hours - 7) / 24.0 * 2 * np.pi)  # daytime peak
    noise = rng.normal(0.0, 12.0, len(index))
    values = np.clip(daily + noise, 1.0, None)
    return pd.Series(values, index=index, name=ENERGY_COL)


def stub_compute(index: pd.DatetimeIndex, *, seed: int = 13) -> pd.Series:
    """Silicon Data stub: realistic mean-reverting H100 price ($/GPU·h, > 0)."""
    rng = np.random.default_rng(seed)
    n = len(index)
    price = np.empty(n)
    level = 2.30  # community H100 market anchor (USD/GPU·h)
    for i in range(n):
        level += 0.05 * (2.30 - level) + rng.normal(0.0, 0.04)  # Ornstein-Uhlenbeck
        price[i] = level
    return pd.Series(np.clip(price, 0.5, None), index=index, name=COMPUTE_COL)


def main() -> None:
    index = _hourly_index(WINDOW_START, WINDOW_END)

    energy = fetch_energy_entsoe(index, REGION)
    source_tag = "entsoe_real"
    if energy is None:
        energy = synthetic_energy(index)
        source_tag = "synthetic_fallback"
    energy.name = ENERGY_COL

    compute = stub_compute(index)

    frame = pd.concat([energy, compute], axis=1)
    frame.index.name = "timestamp"
    frame.attrs["energy_source"] = source_tag
    frame.attrs["compute_source"] = "silicon_data_stub"

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(OUTPUT)
    log.info("Wrote %s (%d rows, energy=%s).", OUTPUT, len(frame), source_tag)


if __name__ == "__main__":
    configure_logging()
    main()
