"""Tests de la boîte à outils de cointégration (Engle-Granger, Johansen, demi-vie, stabilité).

Cas analytiques connus : détection sur un couple cointégré construit, **rejet** sur deux
marches aléatoires indépendantes (anti-spurious), récupération de la demi-vie OU, et
preuve point-in-time de la ré-estimation glissante.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from cointegration import (
    adf_test,
    engle_granger,
    half_life,
    johansen,
    kpss_test,
    rolling_cointegration,
)


def test_engle_granger_detects_known_cointegration(cointegrated_pair) -> None:
    y, x, beta = cointegrated_pair
    result = engle_granger(y, x)
    assert result.is_cointegrated
    assert result.pvalue < 0.05
    assert abs(result.hedge_ratio - beta) < 0.10  # β récupéré ≈ vrai β


def test_engle_granger_rejects_independent_random_walks(independent_random_walks) -> None:
    y, x = independent_random_walks
    result = engle_granger(y, x)
    assert not result.is_cointegrated
    assert result.pvalue > 0.10


def test_adf_flags_unit_root_and_stationary_series(cointegrated_pair) -> None:
    y, x, _ = cointegrated_pair
    # x est I(1) (marche aléatoire) → ADF ne rejette pas la racine unitaire.
    assert not adf_test(x).is_stationary
    # Le résidu de cointégration est stationnaire → ADF rejette la racine unitaire.
    residuals = engle_granger(y, x).residuals
    assert adf_test(residuals).is_stationary


def test_kpss_agrees_on_stationary_residual(cointegrated_pair) -> None:
    y, x, _ = cointegrated_pair
    residuals = engle_granger(y, x).residuals
    # KPSS : hypothèse nulle = stationnarité → on ne la rejette pas pour un résidu stationnaire.
    assert kpss_test(residuals).is_stationary


def test_johansen_finds_one_relation_for_cointegrated_pair(cointegrated_pair) -> None:
    y, x, _ = cointegrated_pair
    frame = pd.concat([y, x], axis=1)
    result = johansen(frame)
    assert result.n_relations >= 1


def test_johansen_finds_no_relation_for_independent_walks(independent_random_walks) -> None:
    y, x = independent_random_walks
    frame = pd.concat([y, x], axis=1)
    result = johansen(frame)
    assert result.n_relations == 0


def test_half_life_recovers_known_ou_half_life(ou_spread_known_half_life) -> None:
    spread, expected_hl = ou_spread_known_half_life
    hl = half_life(spread)
    assert hl > 0.0
    assert abs(hl - expected_hl) / expected_hl < 0.25  # à 25 % près (bruit fini)


def test_rolling_cointegration_is_point_in_time(cointegrated_pair) -> None:
    """La valeur à l'instant i ne doit dépendre QUE des données ≤ i (aucune fuite future)."""
    y, x, _ = cointegrated_pair
    window = 200
    rolling = rolling_cointegration(y, x, window=window)
    assert list(rolling.columns) == ["hedge_ratio", "pvalue"]
    # Re-calcul sur la série tronquée à i : la dernière ligne doit être identique à rolling[i].
    i = 400
    truncated = rolling_cointegration(y.iloc[: i + 1], x.iloc[: i + 1], window=window)
    np.testing.assert_allclose(
        truncated.iloc[-1].to_numpy(), rolling.iloc[i].to_numpy(), rtol=1e-12, atol=1e-12
    )
    # Les premières fenêtres incomplètes sont NaN (pas d'estimation avec < window points).
    assert rolling["hedge_ratio"].iloc[: window - 1].isna().all()
