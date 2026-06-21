"""I/O des variables exogènes (gaz, météo HDD/CDD) + cible spread (P01).

Réel si un token API est présent ; sinon **repli synthétique déterministe**
(seed fixe), loggué — à la manière de P01. Le connecteur réel météo/gaz relève
de `data-engineer` (cf. CONVERGENCE : registre sources CLAUDE.md §3).

Le processus génératif synthétique injecte volontairement un **lead** : l'énergie
(donc le spread) répond au gaz et au HDD *retardés* de ``LEAD_DAYS``. Le pipeline
point-in-time doit retrouver ce lead — c'est la démonstration de méthode, pas une
prétention de réalisme (cf. rule forward-real-simulated : tout est étiqueté SIMULÉ).
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
BALANCE_TEMP_C = 18.0  # température de référence pour HDD/CDD (°C)
LEAD_DAYS = 3  # retard du DGP : l'exogène précède l'énergie de ce nombre de jours
N_DAYS = 540  # ~18 mois quotidiens
WARMUP_DAYS = 60  # amorçage (fenêtres glissantes) avant le 1er instant de décision


class SyntheticExogenousSource:
    """Source exogène en mémoire (implémente le protocole `ExogenousSource`)."""

    def __init__(self, frames: dict[str, pd.DataFrame]) -> None:
        self._frames = frames

    def names(self) -> list[str]:
        return list(self._frames)

    def vintages(self, name: str) -> pd.DataFrame:
        return self._frames[name]


@dataclass(frozen=True)
class ExogenousPanel:
    """Tout ce dont `run_signal` a besoin, déjà aligné."""

    source: ExogenousSource
    spread: pd.Series  # cible (€/GPU·h), indexée par date
    raw: dict[str, pd.DataFrame]  # frames vintage bruts (versionnés DVC)
    decision_index: pd.DatetimeIndex
    mode: str  # "synthetic" | "real"


def _synthetic_drivers(
    rng: np.random.Generator, idx: pd.DatetimeIndex
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Gaz (€/MWh), HDD, CDD synthétiques saisonniers et déterministes."""
    n = len(idx)
    t = np.arange(n)
    season = 10.0 * np.cos(2.0 * np.pi * t / 365.25)  # froid en hiver
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
    """Spread cible (€/GPU·h) via `core.pricing`, mené par les exogènes retardés."""
    n = len(gas)
    # énergie (€/MWh) = base + gaz/HDD RETARDÉS de LEAD_DAYS + bruit → exogène mène.
    energy = (
        40.0
        + 2.0 * gas.shift(LEAD_DAYS)
        + 0.6 * hdd.shift(LEAD_DAYS)
        + rng.normal(scale=1.5, size=n)
    ).bfill()
    # Compute volontairement *peu* bruité au jour-le-jour : sinon son bruit noie la
    # jambe énergie (cost ≈ 0.001275 €/GPU·h par €/MWh) et le lead exogène est invisible.
    # Calibrage illustratif (données SIMULÉES) — pas une prétention de réalisme.
    compute = pd.Series(2.5 + rng.normal(scale=0.005, size=n), index=gas.index)
    return spark_spread_per_gpu_hour(compute, energy).rename("spread")


def _simulate_revision(values: pd.Series, lag: pd.Timedelta) -> pd.DataFrame:
    """Republie un sous-ensemble révisé +1 mois plus tard (exerce le chemin §6c)."""
    sample = values.iloc[WARMUP_DAYS : WARMUP_DAYS + 30] * 1.05  # +5 %, révision tardive
    return from_lagged_series(sample, lag + pd.Timedelta("30D"))


def load_panel(seed: int = DEMO_SEED) -> ExogenousPanel:
    """Charge le panel exogène. Réel si token, sinon synthétique déterministe."""
    token = get_env("EXOGENOUS_API_TOKEN")
    if token:
        logger.info(
            "Token exogène présent mais connecteur réel non câblé (cf. CONVERGENCE) "
            "→ repli synthétique."
        )
    mode = "synthetic"
    logger.info("Source exogène : %s (seed=%d, lead injecté=%d j).", mode, seed, LEAD_DAYS)

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
    decision_index = idx[WARMUP_DAYS : N_DAYS - 10]  # marge pour la cible t+k
    return ExogenousPanel(
        source=SyntheticExogenousSource(frames),
        spread=spread,
        raw=frames,
        decision_index=decision_index,
        mode=mode,
    )
