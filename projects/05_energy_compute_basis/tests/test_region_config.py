"""Tests de la config régionale et de la factory de pricer (P05)."""

from __future__ import annotations

import pandas as pd
import pytest

from region_config import RegionConfig, build_regional_pricer


def test_region_config_rejects_pue_below_one() -> None:
    """Un PUE < 1.0 est physiquement impossible (conso totale ≥ conso IT)."""
    with pytest.raises(ValueError, match="pue"):
        RegionConfig(code="FR", pue=0.9, tdp_w=700.0, n_gpus=8, fx_eur_per_usd=1.0)


def test_region_config_rejects_nonpositive_tdp_and_fx() -> None:
    with pytest.raises(ValueError, match="tdp_w"):
        RegionConfig(code="FR", pue=1.2, tdp_w=0.0, n_gpus=8, fx_eur_per_usd=1.0)
    with pytest.raises(ValueError, match="fx"):
        RegionConfig(code="FR", pue=1.2, tdp_w=700.0, n_gpus=8, fx_eur_per_usd=0.0)


def test_region_config_rejects_nonpositive_n_gpus() -> None:
    with pytest.raises(ValueError, match="n_gpus"):
        RegionConfig(code="FR", pue=1.2, tdp_w=700.0, n_gpus=0, fx_eur_per_usd=1.0)


def test_build_regional_pricer_cost_matches_formula(utc_index: pd.DatetimeIndex) -> None:
    """Le coût du pricer construit = power_kw·pue·energy/1000 (formule canonique P01).

    tdp_w=700 → power_kw=0.7 ; pue=1.5 ; energy=100 €/MWh → coût attendu = 0.105 €/GPU·h.
    revenue = compute_usd · fx = 2.0 · 1.0 = 2.0 → spread = 1.895.
    """
    from core.pricing import DataFramePriceSource

    cfg = RegionConfig(code="FR", pue=1.5, tdp_w=700.0, n_gpus=8, fx_eur_per_usd=1.0)
    pricer = build_regional_pricer(cfg)

    energy = pd.DataFrame({"FR": [100.0]}, index=utc_index[:1])
    compute = pd.DataFrame({"H100": [2.00]}, index=utc_index[:1])
    source = DataFramePriceSource(energy=energy, compute=compute)

    result = pricer.price(source, gpu="H100", region="FR")

    assert result.cost.iloc[0] == pytest.approx(0.105)
    assert result.revenue.iloc[0] == pytest.approx(2.00)
    assert result.spread.iloc[0] == pytest.approx(1.895)
    assert result.pue == pytest.approx(1.5)
