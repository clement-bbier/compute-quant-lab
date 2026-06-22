"""Tests du spread normalisé par TFLOP + bandes de sensibilité PUE (Task A4)."""

from __future__ import annotations

import pandas as pd
import pytest

from core.pricing.efficiency import tflops_fp16
from core.pricing.fx import ConstantFx
from core.pricing.power_model import ServerPowerModel
from core.pricing.pricer import SparkSpreadPricer
from core.pricing.pue_prior import ERCOT_TEXAS_PRIOR
from core.pricing.sources import DataFramePriceSource


def _toy_source() -> DataFramePriceSource:
    idx = pd.date_range("2026-01-01", periods=3, freq="h", tz="UTC")
    energy = pd.DataFrame({"ERCOT": [50.0, 50.0, 50.0]}, index=idx)
    compute = pd.DataFrame({"H100": [2.0, 2.0, 2.0]}, index=idx)
    return DataFramePriceSource(energy, compute)


def _pricer() -> SparkSpreadPricer:
    return SparkSpreadPricer(ServerPowerModel(700, ERCOT_TEXAS_PRIOR, 8), ConstantFx(1.0))


def test_normalized_spread_divides_by_tflops() -> None:
    pricer = _pricer()
    res = pricer.price(_toy_source(), gpu="H100", region="ERCOT")
    norm = pricer.normalized_spread(res)
    assert norm.iloc[0] == pytest.approx(res.spread.iloc[0] / tflops_fp16("H100"))


def test_pue_bands_bracket_central_spread() -> None:
    pricer = _pricer()
    src = _toy_source()
    low, high = pricer.pue_sensitivity(src, gpu="H100", region="ERCOT")
    res = pricer.price(src, gpu="H100", region="ERCOT")
    # PUE plus haut => coût énergie plus haut => spread plus bas (et inversement).
    assert high.spread.iloc[0] <= res.spread.iloc[0] <= low.spread.iloc[0]
    assert low.pue == 1.2
    assert high.pue == 1.8


def test_pue_sensitivity_requires_prior() -> None:
    pricer = SparkSpreadPricer(ServerPowerModel(700, 1.5, 8), ConstantFx(1.0))
    with pytest.raises(ValueError):
        pricer.pue_sensitivity(_toy_source(), gpu="H100", region="ERCOT")
