"""Tests for the inter-region BasisCalculator (P05).

Covers: multi-region basis with known values, PUE sensitivity (documented direction),
anti look-ahead, unit/timezone consistency, construction guardrails.
"""

from __future__ import annotations

import pandas as pd
import pytest

from basis import BasisCalculator, BasisResult
from core.pricing import DataFramePriceSource, SparkSpreadPricer
from region_config import RegionConfig, build_regional_pricer

# Identical PUE across regions → basis arithmetic can be computed by hand.
_FR = RegionConfig(code="FR", pue=1.5, tdp_w=700.0, n_gpus=8, fx_eur_per_usd=1.0)
_DE = RegionConfig(code="DE", pue=1.5, tdp_w=700.0, n_gpus=8, fx_eur_per_usd=1.0)


def _pricers(fr: RegionConfig = _FR, de: RegionConfig = _DE) -> dict[str, SparkSpreadPricer]:
    return {"FR": build_regional_pricer(fr), "DE": build_regional_pricer(de)}


def test_basis_known_values(energy_two_regions: pd.DataFrame, compute_global: pd.DataFrame) -> None:
    """basis[FR] = spread_FR − spread_DE = 0.7·1.5·(energy_DE − energy_FR)/1000.

    power_kw=0.7, pue=1.5 → coefficient 0.00105 €/MWh. energy_DE−energy_FR =
    [-10, 10, 15, -10] → expected basis = [-0.0105, 0.0105, 0.01575, -0.0105].
    """
    source = DataFramePriceSource(energy=energy_two_regions, compute=compute_global)
    calc = BasisCalculator(_pricers(), reference="DE")

    result = calc.compute(source, gpu="H100")

    expected = [-0.0105, 0.0105, 0.01575, -0.0105]
    assert result.basis["FR"].to_list() == pytest.approx(expected)
    assert result.reference == "DE"
    assert set(result.regions) == {"FR", "DE"}


def test_pue_sensitivity_is_monotone(
    energy_two_regions: pd.DataFrame, compute_global: pd.DataFrame
) -> None:
    """↑ PUE_FR ⇒ ↑ cost_FR ⇒ ↓ spread_FR ⇒ ↓ basis_FR at every instant (energy > 0)."""
    source = DataFramePriceSource(energy=energy_two_regions, compute=compute_global)

    base = BasisCalculator(_pricers(), reference="DE").compute(source, gpu="H100")
    fr_high = RegionConfig(code="FR", pue=1.8, tdp_w=700.0, n_gpus=8, fx_eur_per_usd=1.0)
    high = BasisCalculator(_pricers(fr=fr_high), reference="DE").compute(source, gpu="H100")

    assert (high.basis["FR"] < base.basis["FR"]).all()


def test_no_lookahead_future_energy_does_not_change_past_basis(
    energy_two_regions: pd.DataFrame, compute_global: pd.DataFrame
) -> None:
    """Adding a *future* FR energy observation does not change the basis at past instants."""
    source = DataFramePriceSource(energy=energy_two_regions, compute=compute_global)
    base = BasisCalculator(_pricers(), reference="DE").compute(source, gpu="H100")

    future_ts = energy_two_regions.index[-1] + pd.Timedelta(hours=1)
    leaked = energy_two_regions.copy()
    # FR observes an outlier price in the future; DE is not yet known at this instant.
    leaked.loc[future_ts, "FR"] = 9999.0  # must never leak into the past
    source_leaked = DataFramePriceSource(energy=leaked, compute=compute_global)
    after = BasisCalculator(_pricers(), reference="DE").compute(source_leaked, gpu="H100")

    shared = base.basis["FR"].index
    # The past basis is strictly unchanged: no future value leaks backward.
    pd.testing.assert_series_equal(after.basis["FR"].loc[shared], base.basis["FR"])
    # At the future instant, DE is unknown → no usable basis is fabricated (NaN).
    assert pd.isna(after.basis["FR"].loc[future_ts])


def test_basis_units_and_timezone(
    energy_two_regions: pd.DataFrame, compute_global: pd.DataFrame
) -> None:
    source = DataFramePriceSource(energy=energy_two_regions, compute=compute_global)
    result = BasisCalculator(_pricers(), reference="DE").compute(source, gpu="H100")

    assert isinstance(result, BasisResult)
    assert str(result.basis["FR"].index.tz) == "UTC"
    assert str(result.spreads["FR"].index.tz) == "UTC"
    assert result.window == (energy_two_regions.index[0], energy_two_regions.index[-1])
    assert result.pue["FR"] == pytest.approx(1.5)


def test_requires_at_least_two_regions() -> None:
    with pytest.raises(ValueError, match="at least two regions"):
        BasisCalculator({"FR": build_regional_pricer(_FR)}, reference="FR")


def test_reference_must_be_a_known_region() -> None:
    with pytest.raises(ValueError, match="reference"):
        BasisCalculator(_pricers(), reference="XX")
