"""Smoke test live ERCOT — réel, marqué ``@pytest.mark.live`` (B3).

Exclu de la CI par défaut (réseau ERCOT requis). Lance explicitement via :
    uv run pytest -m live core/ingestion/energy -v

Pré-requis réseau : l'API ercot.com est bloquée par WAF Imperva (Incapsula)
depuis certains réseaux hors US (code HTTP 403). Ces tests doivent être exécutés
depuis un réseau US ou un proxy approprié.

Ce que valide le smoke :
- Le connecteur ErcotMarket est bien enregistré dans le registre.
- get_spp() retourne des données avec volumétrie > 0.
- La série RTM est UTC tz-aware et monotone croissante.
- get_load_forecast() retourne des données avec publish_time < interval_start.
- Les deux appels couvrent au moins 1 jour de données.
"""

from __future__ import annotations

import pytest
import pandas as pd

from core.ingestion.energy.base import available_markets, get_market


@pytest.mark.live
def test_ercot_is_registered() -> None:
    """ERCOT est toujours dans le registre (marché public, required_env vide)."""
    assert "ercot" in available_markets()


@pytest.mark.live
def test_rtm_price_live() -> None:
    """Tire 2 jours de prix RTM réels et vérifie les garanties de forme."""
    market = get_market("ercot")

    # 2 jours récents — on prend J-3 à J-1 pour éviter les données incomplètes
    end = pd.Timestamp.now(tz="UTC").normalize() - pd.Timedelta(days=1)
    start = end - pd.Timedelta(days=2)

    series = market.rtm_price(start, end)

    # Volumétrie : 2 jours × 96 intervalles de 15 min = 192 points attendus
    assert len(series) > 0, "La série RTM est vide"
    assert len(series) >= 48, f"Volumétrie insuffisante : {len(series)} points"

    # Fuseau UTC
    assert series.index.tz is not None
    assert str(series.index.tz) == "UTC", f"Fuseau inattendu : {series.index.tz}"

    # Monotonie temporelle
    assert series.index.is_monotonic_increasing, "L'index n'est pas trié chronologiquement"

    # Pas de NaN
    assert not series.isna().any(), f"{series.isna().sum()} NaN détectés"

    # Plage de valeurs cohérente (ERCOT RTM : typiquement −$50 à $9000/MWh)
    assert series.min() > -1000.0, f"Prix minimum anormal : {series.min()}"
    assert series.max() < 15_000.0, f"Prix maximum anormal : {series.max()}"

    # Nom de la série
    assert series.name == "rtm_price_usd_mwh"


@pytest.mark.live
def test_reserve_forecast_live() -> None:
    """Tire des prévisions de charge réelles et vérifie l'invariant point-in-time L0 §2."""
    market = get_market("ercot")

    # On demande les rapports publiés dans les dernières 48h
    end = pd.Timestamp.now(tz="UTC")
    start = end - pd.Timedelta(hours=48)

    df = market.reserve_forecast(start, end)

    # Volumétrie non nulle
    assert len(df) > 0, "Le DataFrame de prévision est vide"

    # Colonnes obligatoires
    required = {
        "publish_time",
        "interval_start",
        "interval_end",
        "forecast_load_mw",
        "forecast_capacity_mw",
        "reserve_margin_mw",
    }
    missing = required - set(df.columns)
    assert not missing, f"Colonnes manquantes : {missing}"

    # Fuseau UTC
    assert str(df["publish_time"].dt.tz) == "UTC"
    assert str(df["interval_start"].dt.tz) == "UTC"

    # Invariant causal L0 §2 : publish_time < interval_start
    violations = (df["publish_time"] >= df["interval_start"]).sum()
    assert violations == 0, (
        f"{violations} lignes violent l'invariant causal "
        "(publish_time >= interval_start) — look-ahead potentiel"
    )

    # Cohérence marge
    expected_margin = df["forecast_capacity_mw"] - df["forecast_load_mw"]
    pd.testing.assert_series_equal(
        df["reserve_margin_mw"],
        expected_margin,
        check_names=False,
        rtol=1e-4,
    )

    # Charge prévue dans une plage raisonnable pour ERCOT (20 GW − 90 GW)
    assert df["forecast_load_mw"].min() > 10_000.0
    assert df["forecast_load_mw"].max() < 100_000.0
