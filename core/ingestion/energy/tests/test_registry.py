"""Tests of the key-gated EnergyMarket registry (B1).

Checks the injection protocol: registration, lookup, key-gating, and the explicit error for an
unknown market.
"""

from __future__ import annotations

import pandas as pd
import pytest

from core.ingestion.energy.base import (
    EnergyMarket,
    available_markets,
    get_market,
    register_market,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _make_dummy_rtm() -> pd.Series:
    idx = pd.date_range("2024-01-15 00:00", periods=4, freq="15min", tz="UTC")
    return pd.Series([35.0, 36.0, 34.5, 37.2], index=idx, name="rtm_price_usd_mwh")


def _make_dummy_forecast() -> pd.DataFrame:
    idx = pd.date_range("2024-01-15 00:00", periods=4, freq="h", tz="UTC")
    return pd.DataFrame(
        {
            "publish_time": pd.Timestamp("2024-01-14 18:00:00", tz="UTC"),
            "forecast_load_mw": [45000.0, 46000.0, 47000.0, 48000.0],
            "forecast_capacity_mw": [70000.0, 70000.0, 70000.0, 70000.0],
            "reserve_margin_mw": [25000.0, 24000.0, 23000.0, 22000.0],
        },
        index=idx,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_register_and_get() -> None:
    """A registered market is retrievable via get_market and detected in available_markets."""

    @register_market("dummy_test")
    class _Dummy:
        name = "dummy_test"
        required_env: tuple[str, ...] = ()

        def rtm_price(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series:
            return _make_dummy_rtm()

        def reserve_forecast(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
            return _make_dummy_forecast()

    assert "dummy_test" in available_markets()
    market = get_market("dummy_test")
    assert isinstance(market, EnergyMarket)


def test_unknown_market_raises() -> None:
    """get_market raises KeyError for an unregistered market."""
    with pytest.raises(KeyError, match="atlantis"):
        get_market("atlantis")


def test_market_without_env_not_listed(monkeypatch: pytest.MonkeyPatch) -> None:
    """A key-gated market is not in available_markets() when its key is missing."""

    @register_market("gated_test")
    class _Gated:
        name = "gated_test"
        required_env: tuple[str, ...] = ("GATED_TEST_API_KEY",)

        def rtm_price(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series:
            return _make_dummy_rtm()

        def reserve_forecast(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
            return _make_dummy_forecast()

    # Without the environment variable, the market is NOT listed
    monkeypatch.delenv("GATED_TEST_API_KEY", raising=False)
    assert "gated_test" not in available_markets()


def test_market_with_env_is_listed(monkeypatch: pytest.MonkeyPatch) -> None:
    """A key-gated market IS listed when all of its keys are present."""

    @register_market("gated_test2")
    class _Gated2:
        name = "gated_test2"
        required_env: tuple[str, ...] = ("GATED_TEST2_API_KEY",)

        def rtm_price(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series:
            return _make_dummy_rtm()

        def reserve_forecast(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
            return _make_dummy_forecast()

    monkeypatch.setenv("GATED_TEST2_API_KEY", "tok_test")
    assert "gated_test2" in available_markets()


def test_protocol_interface_compliant() -> None:
    """The EnergyMarket class is a runtime-checkable Protocol."""

    class _Minimal:
        name = "minimal"
        required_env: tuple[str, ...] = ()

        def rtm_price(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series:
            return _make_dummy_rtm()

        def reserve_forecast(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
            return _make_dummy_forecast()

    assert isinstance(_Minimal(), EnergyMarket)
