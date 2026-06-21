"""I/O P05 : énergie régionale (ENTSO-E réel + repli synthétique) et indice compute (P04).

Frontière réel/synthétique étiquetée (rule forward-real-simulated) : chaque chargeur
renvoie ``(DataFrame, source_label)`` où ``source_label`` distingue le réel (``"entsoe"``,
``"marketplace"``) du repli déterministe (``"synthetic"``). Aucune écriture dans
``data/raw/``. Tout index est UTC tz-aware.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from core.utils.config import SNAPSHOTS_DIR, get_env

log = logging.getLogger("p05.data")

_COMPUTE_ANCHOR_USD = 2.30  # ancrage marché H100 communautaire ($/GPU·h)


def hourly_index(start: str, periods: int) -> pd.DatetimeIndex:
    """Grille horaire UTC tz-aware de ``periods`` points à partir de ``start``."""
    return pd.date_range(start, periods=periods, freq="h", tz="UTC")


# --------------------------------------------------------------------------- énergie


def _synthetic_energy(index: pd.DatetimeIndex, region: str, *, seed: int) -> pd.Series:
    """Repli déterministe : saisonnalité journalière + bruit (€/MWh, ≥ 1)."""
    rng = np.random.default_rng(seed)
    hours = index.hour.to_numpy()
    daily = 90.0 + 35.0 * np.sin((hours - 7) / 24.0 * 2 * np.pi)  # pic en journée
    values = np.clip(daily + rng.normal(0.0, 12.0, len(index)), 1.0, None)
    return pd.Series(values, index=index, name=region)


def _try_entsoe(index: pd.DatetimeIndex, regions: list[str], token: str) -> pd.DataFrame | None:
    """Prix day-ahead réels ENTSO-E par région ; ``None`` au moindre échec (repli global)."""
    try:
        from entsoe import EntsoePandasClient
    except ImportError:
        log.warning("entsoe-py non installé — repli synthétique.")
        return None
    try:
        client = EntsoePandasClient(api_key=token)
        start, end = index[0], index[-1] + pd.Timedelta(hours=1)
        columns: dict[str, pd.Series] = {}
        for region in regions:
            raw = client.query_day_ahead_prices(region, start=start, end=end)
            columns[region] = raw.tz_convert("UTC").reindex(index).ffill().astype(float)
        log.info("ENTSO-E réel récupéré pour %s.", ", ".join(regions))
        return pd.DataFrame(columns, index=index)
    except Exception as exc:  # noqa: BLE001 - repli robuste documenté
        log.warning("Échec ENTSO-E (%s) — repli synthétique.", exc)
        return None


def load_regional_energy(
    index: pd.DatetimeIndex, regions: list[str], *, allow_remote: bool = True
) -> tuple[pd.DataFrame, str]:
    """Charge les prix élec €/MWh par région. Réel ENTSO-E si possible, sinon synthétique.

    Returns
    -------
    tuple[pandas.DataFrame, str]
        DataFrame (colonnes = régions, index UTC) et étiquette ``"entsoe"`` ou ``"synthetic"``.
    """
    token = get_env("ENTSOE_API_TOKEN") or get_env("ENTSOE_API_KEY")
    if allow_remote and token:
        frame = _try_entsoe(index, regions, token)
        if frame is not None:
            return frame, "entsoe"
    # Seeds décorrélés par région : sinon FR == DE → basis identiquement nul à PUE égal.
    columns = {r: _synthetic_energy(index, r, seed=7 + i) for i, r in enumerate(regions)}
    return pd.DataFrame(columns, index=index), "synthetic"


# --------------------------------------------------------------------------- compute


def _synthetic_compute(index: pd.DatetimeIndex, gpu: str, *, seed: int) -> pd.Series:
    """Repli déterministe : prix H100 mean-reverting ($/GPU·h, > 0). Prix GLOBAL (1 colonne)."""
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
    """Charge l'indice compute $/GPU·h (P04). Réel si snapshots accumulés, sinon synthétique.

    Le prix compute est **global** (une seule colonne ``gpu``, partagée par toutes les
    régions) — limite assumée du PoC (cf. CLAUDE.md §risques).
    """
    from core.ingestion import CsvSnapshotStore, InsufficientDataError, build_spot_index

    snapshots = CsvSnapshotStore(Path(snapshot_dir)).load() if Path(snapshot_dir).exists() else []
    if snapshots:
        try:
            now = max(s.snapshotted_at for s in snapshots)
            point = build_spot_index(snapshots, now, gpu)
            log.info(
                "Indice compute réel : %.4f $/GPU·h (%s).", point.price_usd_per_hour, point.method
            )
            series = pd.Series(point.price_usd_per_hour, index=index, name=gpu)
            return pd.DataFrame({gpu: series}), "marketplace"
        except InsufficientDataError:
            log.warning("Snapshots présents mais insuffisants — compute synthétique.")
    series = _synthetic_compute(index, gpu, seed=13)
    return pd.DataFrame({gpu: series}), "synthetic"
