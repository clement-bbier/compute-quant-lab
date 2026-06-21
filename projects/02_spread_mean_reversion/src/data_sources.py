"""Chargement des données du spread énergie↔compute, point-in-time, avec provenance explicite.

Trois responsabilités, toutes branchées sur du **réel** :

- ``load_energy_entsoe`` : prix day-ahead réels ENTSO-E (€/MWh), via ``entsoe-py`` (token-gated).
- ``compute_index_series`` : série $/GPU·h de l'indice spot compute reconstruite des snapshots
  marketplace **réels** accumulés (`core.ingestion.build_spot_index`, point-in-time, no carry-forward).
- ``build_spread`` : assemble les deux jambes via le pricer P01 (`core.pricing.SparkSpreadPricer`).

Toute série porte une :class:`DataProvenance` dont le drapeau ``simulated`` est **obligatoire**
(rule ``forward-real-simulated``) : on ne sert jamais du simulé comme du réel.
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

# Hypothèses énergétiques de la thèse : 8x H100 @ 700 W TDP, PUE 1.82 (≈ 10.2 kW serveur).
_THESIS_TDP_W = 700.0
_THESIS_PUE = 1.82
_THESIS_N_GPUS = 8


@dataclass(frozen=True)
class DataProvenance:
    """Origine d'une série, avec frontière réel/simulé **non optionnelle**.

    Parameters
    ----------
    source : str
        Étiquette auditable de la source (ex. ``"entsoe+vastai"``, ``"synthetic_ou"``).
    simulated : bool
        ``True`` si la série est issue d'un modèle/simulation, ``False`` si elle est réelle.
        Sans valeur par défaut : déclarer l'origine est obligatoire (rule ``forward-real-simulated``).
    units : str
        Unité de la série (par défaut ``"EUR/GPU/h"``).
    """

    source: str
    simulated: bool
    units: str = "EUR/GPU/h"


@dataclass(frozen=True)
class SpreadDataset:
    """Spread à trader + décomposition P01 + provenance (réel/simulé tracé)."""

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
    """Price le spark spread €/GPU·h via P01 à partir des deux jambes alignées.

    ``energy`` (€/MWh, colonnes = régions) et ``compute`` ($/GPU·h, colonnes = GPU) doivent être
    indexés UTC tz-aware. Le pricer aligne le compute sur la grille énergie par jointure as-of
    arrière (anti look-ahead, garanti par P01).
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
    """Série temporelle $/GPU·h de l'indice spot compute, **point-in-time** sur ``grid``.

    Chaque point = ``build_spot_index(as_of)`` sur les snapshots réels (≤ as_of, no carry-forward).
    Les instants sans venue fraîche sont omis (``InsufficientDataError``) plutôt que comblés.
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
    """Prix day-ahead **réels** ENTSO-E (€/MWh, index UTC). Réseau ; token via ``ENTSOE_API_TOKEN``.

    Non testé en unitaire (I/O token-gated, comme les connecteurs marketplace de P04).

    Raises
    ------
    RuntimeError
        Si aucun token n'est fourni ni présent dans l'environnement.
    """
    from entsoe import EntsoePandasClient

    api_token = token or os.environ.get("ENTSOE_API_TOKEN")
    if not api_token:
        raise RuntimeError(
            "ENTSOE_API_TOKEN absent : énergie réelle indisponible (cf. .env.example)."
        )
    client = EntsoePandasClient(api_key=api_token)
    series = client.query_day_ahead_prices(region, start=start, end=end)
    series.index = series.index.tz_convert("UTC")
    return series.rename(region).astype(float)
