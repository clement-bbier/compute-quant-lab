"""Construit le dataset aligné énergie/compute pour le pricer P01.

Jambe **énergie** : prix spot ENTSO-E (FR day-ahead, €/MWh, UTC) si un token est
disponible et `entsoe-py` installé ; sinon **repli synthétique déterministe**
(clairement loggué) pour que le pipeline reste reproductible hors-ligne.

Jambe **compute** : *stub* Silicon Data réaliste (H100, $/GPU·h) tant que l'accès
n'est pas confirmé — le swap vers le flux réel est trivial (une fonction).

Sortie : ``data/interim/aligned_spark.parquet`` (grille horaire UTC, co-timestampée,
lag=0), versionnée via ``dvc add``. Aucune écriture dans ``data/raw/`` (immuable).
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("prepare_dataset")

# Racine du dépôt : ce fichier est à projects/01_digital_spark_spread/src/.
REPO_ROOT = Path(__file__).resolve().parents[3]
OUTPUT = REPO_ROOT / "data" / "interim" / "aligned_spark.parquet"

REGION = "FR"
WINDOW_START = "2025-01-01"
WINDOW_END = "2025-02-01"  # exclu : un mois de données horaires
ENERGY_COL = "energy_eur_per_mwh"
COMPUTE_COL = "compute_usd_per_gpu_h"


def _hourly_index(start: str, end: str) -> pd.DatetimeIndex:
    """Grille horaire UTC tz-aware, bord droit exclu."""
    return pd.date_range(start, end, freq="h", tz="UTC", inclusive="left")


def fetch_energy_entsoe(index: pd.DatetimeIndex, region: str) -> pd.Series | None:
    """Tente de récupérer le prix day-ahead réel ENTSO-E. None si indisponible."""
    token = os.environ.get("ENTSOE_API_TOKEN") or os.environ.get("ENTSOE_API_KEY")
    if not token:
        log.warning("Pas de token ENTSO-E (ENTSOE_API_TOKEN) — repli synthétique.")
        return None
    try:
        from entsoe import EntsoePandasClient
    except ImportError:
        log.warning("entsoe-py non installé — repli synthétique.")
        return None
    try:
        client = EntsoePandasClient(api_key=token)
        start = pd.Timestamp(WINDOW_START, tz="UTC")
        end = pd.Timestamp(WINDOW_END, tz="UTC")
        raw = client.query_day_ahead_prices(region, start=start, end=end)
        series = raw.tz_convert("UTC").reindex(index).ffill()
        log.info("ENTSO-E réel récupéré : %d points (%s).", series.notna().sum(), region)
        return series.astype(float)
    except Exception as exc:  # noqa: BLE001 - repli robuste documenté
        log.warning("Échec ENTSO-E (%s) — repli synthétique.", exc)
        return None


def synthetic_energy(index: pd.DatetimeIndex, *, seed: int = 7) -> pd.Series:
    """Repli déterministe : saisonnalité journalière + bruit (€/MWh, ≥ 0)."""
    rng = np.random.default_rng(seed)
    hours = index.hour.to_numpy()
    daily = 90.0 + 35.0 * np.sin((hours - 7) / 24.0 * 2 * np.pi)  # pic en journée
    noise = rng.normal(0.0, 12.0, len(index))
    values = np.clip(daily + noise, 1.0, None)
    return pd.Series(values, index=index, name=ENERGY_COL)


def stub_compute(index: pd.DatetimeIndex, *, seed: int = 13) -> pd.Series:
    """Stub Silicon Data : prix H100 mean-reverting réaliste ($/GPU·h, > 0)."""
    rng = np.random.default_rng(seed)
    n = len(index)
    price = np.empty(n)
    level = 2.30  # ancrage marché H100 communautaire (USD/GPU·h)
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
    log.info("Écrit %s (%d lignes, énergie=%s).", OUTPUT, len(frame), source_tag)

    _dvc_add(OUTPUT)


def _dvc_add(path: Path) -> None:
    """Versionne l'artefact via DVC si disponible (sinon avertit, sans bloquer)."""
    try:
        subprocess.run(
            [sys.executable, "-m", "dvc", "add", str(path)],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        log.info("dvc add OK : %s.dvc", path.name)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        log.warning("dvc add non effectué (%s) — à versionner à la convergence.", exc)


if __name__ == "__main__":
    main()
