"""P05 I/O: regional energy (real ENTSO-E + synthetic fallback) and compute index (P04).

Labeled real/synthetic boundary (rule forward-real-simulated): each loader returns
``(DataFrame, source_label)`` where ``source_label`` distinguishes real (``"entsoe"``,
``"marketplace"``) from the deterministic fallback (``"synthetic"``). No writes to
``data/raw/``. Every index is UTC tz-aware.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from core.utils.config import SNAPSHOTS_DIR, get_env

log = logging.getLogger("p05.data")

_COMPUTE_ANCHOR_USD = 2.30  # community H100 market anchor ($/GPU·h)


def hourly_index(start: str, periods: int) -> pd.DatetimeIndex:
    """UTC tz-aware hourly grid of ``periods`` points starting at ``start``."""
    return pd.date_range(start, periods=periods, freq="h", tz="UTC")


# --------------------------------------------------------------------------- energy


def _synthetic_energy(index: pd.DatetimeIndex, region: str, *, seed: int) -> pd.Series:
    """Deterministic fallback: daily seasonality + noise (€/MWh, ≥ 1)."""
    rng = np.random.default_rng(seed)
    hours = index.hour.to_numpy()
    daily = 90.0 + 35.0 * np.sin((hours - 7) / 24.0 * 2 * np.pi)  # daytime peak
    values = np.clip(daily + rng.normal(0.0, 12.0, len(index)), 1.0, None)
    return pd.Series(values, index=index, name=region)


def _try_entsoe(index: pd.DatetimeIndex, regions: list[str], token: str) -> pd.DataFrame | None:
    """Real ENTSO-E day-ahead prices per region; ``None`` on any failure (global fallback)."""
    try:
        from entsoe import EntsoePandasClient
    except ImportError:
        log.warning("entsoe-py not installed — falling back to synthetic.")
        return None
    try:
        client = EntsoePandasClient(api_key=token)
        start, end = index[0], index[-1] + pd.Timedelta(hours=1)
        columns: dict[str, pd.Series] = {}
        for region in regions:
            raw = client.query_day_ahead_prices(region, start=start, end=end)
            columns[region] = raw.tz_convert("UTC").reindex(index).ffill().astype(float)
        log.info("Real ENTSO-E data retrieved for %s.", ", ".join(regions))
        return pd.DataFrame(columns, index=index)
    except Exception as exc:  # noqa: BLE001 - documented robust fallback
        log.warning("ENTSO-E failure (%s) — falling back to synthetic.", exc)
        return None


def load_regional_energy(
    index: pd.DatetimeIndex, regions: list[str], *, allow_remote: bool = True
) -> tuple[pd.DataFrame, str]:
    """Loads €/MWh electricity prices per region. Real ENTSO-E if possible, else synthetic.

    Returns
    -------
    tuple[pandas.DataFrame, str]
        DataFrame (columns = regions, UTC index) and label ``"entsoe"`` or ``"synthetic"``.
    """
    token = get_env("ENTSOE_API_TOKEN") or get_env("ENTSOE_API_KEY")
    if allow_remote and token:
        frame = _try_entsoe(index, regions, token)
        if frame is not None:
            return frame, "entsoe"
    # Decorrelated seeds per region: otherwise FR == DE → basis identically zero at equal PUE.
    columns = {r: _synthetic_energy(index, r, seed=7 + i) for i, r in enumerate(regions)}
    return pd.DataFrame(columns, index=index), "synthetic"


# --------------------------------------------------------------------------- compute


def _synthetic_compute(index: pd.DatetimeIndex, gpu: str, *, seed: int) -> pd.Series:
    """Deterministic fallback: mean-reverting H100 price ($/GPU·h, > 0). GLOBAL price (1 column)."""
    rng = np.random.default_rng(seed)
    n = len(index)
    price = np.empty(n)
    level = _COMPUTE_ANCHOR_USD
    for i in range(n):
        level += 0.05 * (_COMPUTE_ANCHOR_USD - level) + rng.normal(0.0, 0.04)  # OU
        price[i] = level
    return pd.Series(np.clip(price, 0.5, None), index=index, name=gpu)


def load_compute_index(
    index: pd.DatetimeIndex, gpu: str, *, snapshot_dir: Path = SNAPSHOTS_DIR
) -> tuple[pd.DataFrame, str]:
    """Loads the $/GPU·h compute index (P04). Real if snapshots accumulated, else synthetic.

    The compute price is **global** (a single ``gpu`` column, shared across all
    regions) — an acknowledged PoC limitation (see CLAUDE.md §risks).
    """
    from core.ingestion import CsvSnapshotStore, InsufficientDataError, build_spot_index

    snapshots = CsvSnapshotStore(Path(snapshot_dir)).load() if Path(snapshot_dir).exists() else []
    if snapshots:
        try:
            now = max(s.snapshotted_at for s in snapshots)
            point = build_spot_index(snapshots, now, gpu)
            log.info(
                "Real compute index: %.4f $/GPU·h (%s).", point.price_usd_per_hour, point.method
            )
            series = pd.Series(point.price_usd_per_hour, index=index, name=gpu)
            return pd.DataFrame({gpu: series}), "marketplace"
        except InsufficientDataError:
            log.warning("Snapshots present but insufficient — falling back to synthetic compute.")
    series = _synthetic_compute(index, gpu, seed=13)
    return pd.DataFrame({gpu: series}), "synthetic"
