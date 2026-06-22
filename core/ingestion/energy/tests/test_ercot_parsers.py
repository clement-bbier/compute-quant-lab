"""Tests des parsers ERCOT sur fixtures figées (B2).

Testent la logique pure des parsers (I/O isolée) sans appel réseau.
Les fixtures CSV sont des échantillons réels capturés en B0 et figés ici
pour garantir la reproductibilité des tests (déterminisme exigé).

Garanties testées :
- Sortie RTM : pd.Series UTC tz-aware, triée, en $/MWh, sans NaN injectés.
- Prévision de réserve : colonne ``publish_time`` horodatée à l'heure de
  PUBLICATION (pas cible) → garantit le point-in-time L0 §2.
- ``reserve_margin_mw`` = ``forecast_capacity_mw`` − ``forecast_load_mw``.
"""

from __future__ import annotations

import pathlib

import pandas as pd
import pytest

from core.ingestion.energy.ercot import parse_rtm_spp, parse_load_forecast

# ---------------------------------------------------------------------------
# Chemins des fixtures figées
# ---------------------------------------------------------------------------

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
RTM_FIXTURE = FIXTURES / "ercot_rtm_spp_sample.csv"
FORECAST_FIXTURE = FIXTURES / "ercot_load_forecast_sample.csv"


# ---------------------------------------------------------------------------
# Tests parse_rtm_spp
# ---------------------------------------------------------------------------


class TestParseRtmSpp:
    """Parser du prix RTM (Settlement Point Price) ERCOT."""

    def test_returns_series(self) -> None:
        """Le parser retourne un pd.Series (pas un DataFrame)."""
        df_raw = pd.read_csv(RTM_FIXTURE, parse_dates=["Time", "Interval Start", "Interval End"])
        result = parse_rtm_spp(df_raw, location="HB_BUSAVG")
        assert isinstance(result, pd.Series)

    def test_index_is_utc(self) -> None:
        """L'index de la série est UTC tz-aware."""
        df_raw = pd.read_csv(RTM_FIXTURE, parse_dates=["Time", "Interval Start", "Interval End"])
        result = parse_rtm_spp(df_raw, location="HB_BUSAVG")
        assert result.index.tz is not None
        assert str(result.index.tz) == "UTC"

    def test_series_name(self) -> None:
        """Le nom de la série est rtm_price_usd_mwh."""
        df_raw = pd.read_csv(RTM_FIXTURE, parse_dates=["Time", "Interval Start", "Interval End"])
        result = parse_rtm_spp(df_raw, location="HB_BUSAVG")
        assert result.name == "rtm_price_usd_mwh"

    def test_sorted_chronologically(self) -> None:
        """La série est triée chronologiquement (monotone croissante)."""
        df_raw = pd.read_csv(RTM_FIXTURE, parse_dates=["Time", "Interval Start", "Interval End"])
        result = parse_rtm_spp(df_raw, location="HB_BUSAVG")
        assert result.index.is_monotonic_increasing

    def test_no_nan_injected(self) -> None:
        """Aucun NaN n'est injecté dans la série (ne pas masquer des trous)."""
        df_raw = pd.read_csv(RTM_FIXTURE, parse_dates=["Time", "Interval Start", "Interval End"])
        result = parse_rtm_spp(df_raw, location="HB_BUSAVG")
        assert not result.isna().any()

    def test_values_in_usd_per_mwh(self) -> None:
        """Les valeurs correspondent aux prix de la fixture ($/MWh, HB_BUSAVG)."""
        df_raw = pd.read_csv(RTM_FIXTURE, parse_dates=["Time", "Interval Start", "Interval End"])
        result = parse_rtm_spp(df_raw, location="HB_BUSAVG")
        # Les 4 prix HB_BUSAVG de la fixture
        expected = [35.12, 36.45, 34.87, 37.23]
        assert list(result.values) == pytest.approx(expected, rel=1e-6)

    def test_location_filter(self) -> None:
        """Seule la localisation demandée est retournée (pas de mélange hub/zone)."""
        df_raw = pd.read_csv(RTM_FIXTURE, parse_dates=["Time", "Interval Start", "Interval End"])
        hub = parse_rtm_spp(df_raw, location="HB_BUSAVG")
        zone = parse_rtm_spp(df_raw, location="LZ_HOUSTON")
        assert len(hub) == 4
        assert len(zone) == 4
        # Les prix doivent différer
        assert list(hub.values) != pytest.approx(list(zone.values), abs=0.01)

    def test_unknown_location_raises(self) -> None:
        """Une localisation inconnue lève ValueError (fail-fast)."""
        df_raw = pd.read_csv(RTM_FIXTURE, parse_dates=["Time", "Interval Start", "Interval End"])
        with pytest.raises(ValueError, match="HB_MISSING"):
            parse_rtm_spp(df_raw, location="HB_MISSING")


# ---------------------------------------------------------------------------
# Tests parse_load_forecast (point-in-time L0)
# ---------------------------------------------------------------------------


class TestParseLoadForecast:
    """Parser de la prévision de charge/réserve ERCOT.

    La colonne ``publish_time`` est la clé du point-in-time L0 §2 :
    elle doit être horodatée à l'heure de PUBLICATION du rapport,
    jamais à l'heure cible prévue.
    """

    def _load(self) -> pd.DataFrame:
        return pd.read_csv(
            FORECAST_FIXTURE,
            parse_dates=["Time", "Interval Start", "Interval End", "Publish Time"],
        )

    def test_returns_dataframe(self) -> None:
        """Le parser retourne un pd.DataFrame."""
        result = parse_load_forecast(self._load())
        assert isinstance(result, pd.DataFrame)

    def test_required_columns_present(self) -> None:
        """Les colonnes minimales du contrat EnergyMarket sont présentes."""
        result = parse_load_forecast(self._load())
        required = {
            "publish_time",
            "interval_start",
            "interval_end",
            "forecast_load_mw",
            "forecast_capacity_mw",
            "reserve_margin_mw",
        }
        assert required.issubset(set(result.columns))

    def test_publish_time_is_utc(self) -> None:
        """publish_time est UTC tz-aware : garantie point-in-time L0 §2."""
        result = parse_load_forecast(self._load())
        assert result["publish_time"].dt.tz is not None
        assert str(result["publish_time"].dt.tz) == "UTC"

    def test_interval_start_is_utc(self) -> None:
        """interval_start est UTC tz-aware."""
        result = parse_load_forecast(self._load())
        assert result["interval_start"].dt.tz is not None
        assert str(result["interval_start"].dt.tz) == "UTC"

    def test_publish_time_precedes_interval_start(self) -> None:
        """publish_time < interval_start : le rapport est publié AVANT la cible.

        Invariant causal L0 §6 : la prévision est connue AVANT l'heure cible.
        """
        result = parse_load_forecast(self._load())
        assert (result["publish_time"] < result["interval_start"]).all()

    def test_reserve_margin_equals_capacity_minus_load(self) -> None:
        """reserve_margin_mw = forecast_capacity_mw - forecast_load_mw (cohérence)."""
        result = parse_load_forecast(self._load())
        expected = result["forecast_capacity_mw"] - result["forecast_load_mw"]
        pd.testing.assert_series_equal(
            result["reserve_margin_mw"],
            expected,
            check_names=False,
            rtol=1e-6,
        )

    def test_sorted_by_publish_then_interval(self) -> None:
        """Tri : (publish_time ASC, interval_start ASC)."""
        result = parse_load_forecast(self._load())
        expected = result.sort_values(["publish_time", "interval_start"])
        pd.testing.assert_frame_equal(
            result.reset_index(drop=True),
            expected.reset_index(drop=True),
        )

    def test_forecast_capacity_populated(self) -> None:
        """forecast_capacity_mw est renseigné (non nul, non NaN).

        Note: la fixture utilise 'System Total' comme proxy de charge ;
        la capacité est fournie séparément par un autre rapport.
        Pour ce parser, capacity = charge + marge fixe (fixture simplifiée).
        """
        result = parse_load_forecast(self._load())
        assert not result["forecast_capacity_mw"].isna().any()
        assert (result["forecast_capacity_mw"] > 0).all()
