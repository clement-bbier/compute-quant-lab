"""Données synthétiques déterministes pour le PoC P09 (strictement SIMULÉES).

Au PoC, on ne dépend pas d'ENTSO-E : on fabrique un spark spread **pricé par P01** dont la
direction future porte un signal **modeste mais réel** mené par une variable exogène (prix
du gaz), connue avec un lag de publication via la mécanique vintage de **P07**. Objectif :
exercer tout le pipeline (features point-in-time → purged-CV → backtest P08) sur un cas où
un modèle honnête trouve un petit edge — ni un oracle parfait, ni du bruit pur.

Contraintes respectées :
* spread **strictement positif** (le PnL de P08 est en rendement relatif ``prix[t]/prix[t-1]``,
  qui exploserait près de zéro) — cf. `core.backtest.reference_loop` ;
* provenance ``simulated`` **obligatoire** (rule ``forward-real-simulated``) ;
* horodatages UTC, grille journalière (les lags gaz/HDD de P07 sont en jours).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from core.features import DEFAULT_PUBLICATION_LAGS, from_lagged_series
from core.pricing import ServerSpec, energy_cost_per_gpu_hour, spark_spread_per_gpu_hour

#: Graine unique du générateur (reproductibilité).
SEED: int = 42

# --- Paramètres de la dynamique du spread (choisis pour un edge MODESTE, anti-illusion) ---
_MU: float = 2.3  # niveau d'équilibre du spread (€/GPU·h), réaliste H100
_KAPPA: float = 0.02  # vitesse de retour à la moyenne (faible → peu de signal trivial)
_SIGMA: float = 0.06  # bruit par pas (domine le signal → accuracy modeste attendue)
_DELTA: float = 0.025  # poids du lead exogène (gaz) sur le prochain mouvement
_FLOOR: float = 0.5  # plancher de sécurité : garde le spread > 0 pour le PnL relatif


@dataclass(frozen=True)
class DataProvenance:
    """Traçabilité réel/simulé. ``simulated`` est **obligatoire** (rule du labo)."""

    source: str
    simulated: bool  # sans valeur par défaut : un appelant DOIT se prononcer


class InMemoryExogenousSource:
    """Source exogène en mémoire (implémente `ExogenousSource` de P07) servant des vintages."""

    def __init__(self, vintages: dict[str, pd.DataFrame]) -> None:
        self._vintages = vintages

    def names(self) -> list[str]:
        return list(self._vintages)

    def vintages(self, name: str) -> pd.DataFrame:
        return self._vintages[name]


@dataclass(frozen=True)
class SyntheticDataset:
    """Sortie du générateur : spread P01, source exogène P07, provenance."""

    spread: pd.Series
    exog_source: InMemoryExogenousSource
    provenance: DataProvenance


def generate(*, n_days: int = 2200, seed: int = SEED) -> SyntheticDataset:
    """Génère un dataset synthétique déterministe (spread P01 + exogènes P07 lagués).

    Le mouvement du spread vers ``t`` est mené par le gaz **connu à la décision précédente** :
    à l'instant de décision ``d``, la feature ``gas_lag0`` (dernier millésime publié) prédit
    donc partiellement le signe du mouvement ``d → d+1``. Edge faible (cf. ``_DELTA``/``_SIGMA``).
    """
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2019-01-01", periods=n_days, freq="D", tz="UTC")
    spec = ServerSpec()

    # Jambe énergie : marche aléatoire bornée (€/MWh).
    energy = np.clip(120.0 + np.cumsum(rng.standard_normal(n_days) * 3.0), 20.0, None)

    # Exogènes : gaz (lead réel) + HDD (bruit exogène, distracteur honnête).
    gas = np.clip(30.0 + np.cumsum(rng.standard_normal(n_days) * 1.0), 5.0, None)
    hdd = np.clip(rng.normal(10.0, 5.0, n_days), 0.0, None)
    gas_std = (gas - gas.mean()) / gas.std()

    # Spread = retour à la moyenne + lead exogène lagué + bruit. spread[t] dépend du gaz
    # connu à la décision t-1 (gas_std[t-2]) → gas_lag0 à la décision d prédit d → d+1.
    eps = rng.standard_normal(n_days)
    spread_latent = np.empty(n_days, dtype=np.float64)
    spread_latent[0] = _MU
    for t in range(1, n_days):
        driver = gas_std[t - 2] if t >= 2 else 0.0
        spread_latent[t] = (
            spread_latent[t - 1]
            + _KAPPA * (_MU - spread_latent[t - 1])
            + _DELTA * driver
            + _SIGMA * eps[t]
        )
    spread_latent = np.clip(spread_latent, _FLOOR, None)

    # Pricing PAR P01 : compute = coût énergétique + spread, puis on re-price le spread
    # (round-trip) — on consomme réellement core.pricing, on ne le réimplémente pas.
    energy_cost = np.array([energy_cost_per_gpu_hour(e, spec) for e in energy])
    compute_price = energy_cost + spread_latent
    spread = np.array(
        [spark_spread_per_gpu_hour(c, e, spec) for c, e in zip(compute_price, energy)]
    )
    spread_series = pd.Series(spread, index=idx, name="spark_spread")

    exog_source = InMemoryExogenousSource(
        {
            "gas_price": from_lagged_series(
                pd.Series(gas, index=idx), DEFAULT_PUBLICATION_LAGS["gas_price"]
            ),
            "hdd": from_lagged_series(pd.Series(hdd, index=idx), DEFAULT_PUBLICATION_LAGS["hdd"]),
        }
    )
    provenance = DataProvenance(source="synthetic_spark_spread_gas_lead", simulated=True)
    return SyntheticDataset(spread=spread_series, exog_source=exog_source, provenance=provenance)


__all__ = [
    "SEED",
    "DataProvenance",
    "InMemoryExogenousSource",
    "SyntheticDataset",
    "generate",
]
