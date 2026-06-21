"""Tests du BasisCalculator inter-régions (P05).

Couvre : basis multi-région à valeurs connues, sensibilité PUE (direction documentée),
anti look-ahead, cohérence unités/fuseau, garde-fous de construction.
"""

from __future__ import annotations

import pandas as pd
import pytest

from basis import BasisCalculator, BasisResult
from core.pricing import DataFramePriceSource, SparkSpreadPricer
from region_config import RegionConfig, build_regional_pricer

# PUE identiques entre régions → arithmétique du basis calculable à la main.
_FR = RegionConfig(code="FR", pue=1.5, tdp_w=700.0, n_gpus=8, fx_eur_per_usd=1.0)
_DE = RegionConfig(code="DE", pue=1.5, tdp_w=700.0, n_gpus=8, fx_eur_per_usd=1.0)


def _pricers(fr: RegionConfig = _FR, de: RegionConfig = _DE) -> dict[str, SparkSpreadPricer]:
    return {"FR": build_regional_pricer(fr), "DE": build_regional_pricer(de)}


def test_basis_known_values(energy_two_regions: pd.DataFrame, compute_global: pd.DataFrame) -> None:
    """basis[FR] = spread_FR − spread_DE = 0.7·1.5·(energy_DE − energy_FR)/1000.

    power_kw=0.7, pue=1.5 → coefficient 0.00105 €/MWh. energy_DE−energy_FR =
    [-10, 10, 15, -10] → basis attendu = [-0.0105, 0.0105, 0.01575, -0.0105].
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
    """↑ PUE_FR ⇒ ↑ coût_FR ⇒ ↓ spread_FR ⇒ ↓ basis_FR à chaque instant (énergie > 0)."""
    source = DataFramePriceSource(energy=energy_two_regions, compute=compute_global)

    base = BasisCalculator(_pricers(), reference="DE").compute(source, gpu="H100")
    fr_high = RegionConfig(code="FR", pue=1.8, tdp_w=700.0, n_gpus=8, fx_eur_per_usd=1.0)
    high = BasisCalculator(_pricers(fr=fr_high), reference="DE").compute(source, gpu="H100")

    assert (high.basis["FR"] < base.basis["FR"]).all()


def test_no_lookahead_future_energy_does_not_change_past_basis(
    energy_two_regions: pd.DataFrame, compute_global: pd.DataFrame
) -> None:
    """Ajouter une obs énergie FR *future* ne modifie pas le basis aux instants passés."""
    source = DataFramePriceSource(energy=energy_two_regions, compute=compute_global)
    base = BasisCalculator(_pricers(), reference="DE").compute(source, gpu="H100")

    future_ts = energy_two_regions.index[-1] + pd.Timedelta(hours=1)
    leaked = energy_two_regions.copy()
    # FR observe un prix aberrant dans le futur ; DE n'est pas encore connu à cet instant.
    leaked.loc[future_ts, "FR"] = 9999.0  # ne doit jamais fuiter vers le passé
    source_leaked = DataFramePriceSource(energy=leaked, compute=compute_global)
    after = BasisCalculator(_pricers(), reference="DE").compute(source_leaked, gpu="H100")

    shared = base.basis["FR"].index
    # Le basis passé est strictement inchangé : aucune valeur future ne fuit en arrière.
    pd.testing.assert_series_equal(after.basis["FR"].loc[shared], base.basis["FR"])
    # À l'instant futur, DE est inconnu → aucun basis exploitable n'est fabriqué (NaN).
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
    with pytest.raises(ValueError, match="deux régions"):
        BasisCalculator({"FR": build_regional_pricer(_FR)}, reference="FR")


def test_reference_must_be_a_known_region() -> None:
    with pytest.raises(ValueError, match="reference"):
        BasisCalculator(_pricers(), reference="XX")
