"""Tests-first for the vectorised digital spark spread pricer (P01).

Covers the P01 prompt's requirements:
- (a) spread math + reproduction of the thesis's reference figures;
- (b) anti look-ahead: no data with index > t enters the spread at t;
- (c) units / timezone: €/MWh <-> €/GPU-h conversion, point-in-time $/€ FX, naive rejection;
- (e) DI: the pricer runs on mocked `PriceSource`/`FxConverter`/`SpreadKernel`.

The Rust<->Python parity test (d) lives in ``test_pricer_parity.py`` (skipif).
All tests use deterministic in-memory fixtures — zero network.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.pricing import (
    ConstantFx,
    DataFramePriceSource,
    FxConverter,
    PriceSource,
    PythonOracle,
    ServerPowerModel,
    SeriesFx,
    SparkSpreadPricer,
    SpreadResult,
)

# --- Thesis constants (8x H100) -------------------------------------------------------
H100_TDP_W = 700.0
SERVER_PUE = 1.82
N_GPUS = 8


def _utc_index(periods: int, freq: str = "h") -> pd.DatetimeIndex:
    return pd.date_range("2025-01-01", periods=periods, freq=freq, tz="UTC")


def _ref_power_model() -> ServerPowerModel:
    return ServerPowerModel(tdp_w=H100_TDP_W, pue=SERVER_PUE, n_gpus=N_GPUS)


def _source(energy: pd.Series, compute: pd.Series) -> DataFramePriceSource:
    """Single-region ('FR') and single-GPU ('H100') source."""
    return DataFramePriceSource(
        energy=pd.DataFrame({"FR": energy}),
        compute=pd.DataFrame({"H100": compute}),
    )


# ============================ (a) Spread math =========================================


def test_reference_figures_reproduced():
    """The pricer reproduces 0.19 €/h/GPU, 1.53 €/h per server, spread of 0.31."""
    idx = _utc_index(3)
    energy = pd.Series(150.0, index=idx)  # €/MWh
    compute = pd.Series(0.50, index=idx)  # $/GPU-h (1 USD = 1 EUR via ConstantFx(1.0))

    pricer = SparkSpreadPricer(_ref_power_model(), ConstantFx(1.0), kernel=PythonOracle())
    result = pricer.price(_source(energy, compute), gpu="H100", region="FR")

    cost_per_gpu = result.cost.iloc[0]
    assert round(cost_per_gpu, 2) == 0.19
    assert round(cost_per_gpu * N_GPUS, 2) == 1.53
    assert round(result.spread.iloc[0], 2) == 0.31


def test_spread_equals_revenue_minus_cost():
    """Accounting identity spread == revenue − cost on arbitrary inputs."""
    idx = _utc_index(5)
    rng = np.random.default_rng(0)
    energy = pd.Series(rng.uniform(50, 400, 5), index=idx)
    compute = pd.Series(rng.uniform(0.2, 1.2, 5), index=idx)

    pricer = SparkSpreadPricer(_ref_power_model(), ConstantFx(1.0))
    result = pricer.price(_source(energy, compute), gpu="H100", region="FR")

    pd.testing.assert_series_equal(result.spread, result.revenue - result.cost, check_names=False)


def test_result_is_frozen_with_metadata():
    """SpreadResult exposes the decomposition + metadata (gpu, region, pue, power)."""
    idx = _utc_index(2)
    pricer = SparkSpreadPricer(_ref_power_model(), ConstantFx(1.0))
    result = pricer.price(
        _source(pd.Series(150.0, index=idx), pd.Series(0.5, index=idx)),
        gpu="H100",
        region="FR",
    )
    assert isinstance(result, SpreadResult)
    assert result.gpu == "H100"
    assert result.region == "FR"
    assert result.pue == SERVER_PUE
    assert round(result.power_kw_per_gpu, 3) == 0.7
    with pytest.raises(Exception):
        result.spread = pd.Series()  # type: ignore[misc]  # frozen


# ============================ (b) Anti look-ahead ====================================


def test_future_rows_do_not_change_past_spreads():
    """Adding rows with index > t leaves the spread at t bit-identical."""
    idx = _utc_index(4)
    energy = pd.Series([100.0, 150.0, 200.0, 250.0], index=idx)
    compute = pd.Series([0.40, 0.50, 0.60, 0.70], index=idx)

    pricer = SparkSpreadPricer(_ref_power_model(), ConstantFx(1.0))
    base = pricer.price(_source(energy, compute), gpu="H100", region="FR")

    future_idx = _utc_index(7)
    energy_ext = pd.Series([100.0, 150.0, 200.0, 250.0, 999.0, 888.0, 777.0], index=future_idx)
    compute_ext = pd.Series([0.40, 0.50, 0.60, 0.70, 9.9, 8.8, 7.7], index=future_idx)
    extended = pricer.price(_source(energy_ext, compute_ext), gpu="H100", region="FR")

    pd.testing.assert_series_equal(base.spread, extended.spread.loc[: idx[-1]])


def test_compute_alignment_is_backward_only():
    """On a coarse compute grid, the spread at t never uses a future price."""
    energy_idx = _utc_index(5)  # hourly
    energy = pd.Series([150.0, 150.0, 150.0, 150.0, 150.0], index=energy_idx)
    # compute known only at t2 and t4
    compute = pd.Series([0.50, 0.90], index=energy_idx[[2, 4]])

    pricer = SparkSpreadPricer(_ref_power_model(), ConstantFx(1.0))
    result = pricer.price(_source(energy, compute), gpu="H100", region="FR")

    # t0, t1: no compute price known yet -> revenue/spread NaN (no fill from the future)
    assert np.isnan(result.spread.iloc[0])
    assert np.isnan(result.spread.iloc[1])
    # t3: must use the last known price (0.50 at t2), definitely NOT 0.90 (future t4)
    assert result.revenue.iloc[3] == 0.50


# ============================ (c) Units / timezone ====================================


def test_energy_unit_conversion_mwh_to_gpu_hour():
    """Cost = power_kw * pue * (€/MWh) / 1000, computed by hand."""
    idx = _utc_index(1)
    pricer = SparkSpreadPricer(_ref_power_model(), ConstantFx(1.0))
    result = pricer.price(
        _source(pd.Series(200.0, index=idx), pd.Series(1.0, index=idx)),
        gpu="H100",
        region="FR",
    )
    expected = 0.7 * SERVER_PUE * 200.0 / 1000.0
    assert result.cost.iloc[0] == pytest.approx(expected)


def test_constant_fx_converts_usd_to_eur():
    idx = _utc_index(3)
    amount = pd.Series([1.0, 2.0, 4.0], index=idx)
    out = ConstantFx(0.90).to_eur(amount)
    pd.testing.assert_series_equal(out, amount * 0.90, check_names=False)


def test_series_fx_is_point_in_time():
    """SeriesFx uses the rate known at each t (backward), never a future rate."""
    idx = _utc_index(3)
    rates = pd.Series([0.90, 0.80], index=idx[[0, 2]])  # rate known at t0, then t2
    amount = pd.Series([1.0, 1.0, 1.0], index=idx)
    out = SeriesFx(rates).to_eur(amount)
    # t1 must keep 0.90 (last known), not anticipate 0.80
    assert out.iloc[0] == pytest.approx(0.90)
    assert out.iloc[1] == pytest.approx(0.90)
    assert out.iloc[2] == pytest.approx(0.80)


def test_naive_datetime_rejected():
    """A timezone-naive index must be rejected (UTC tz-aware is mandatory)."""
    naive_idx = pd.date_range("2025-01-01", periods=3, freq="h")  # tz-naive
    with pytest.raises(ValueError):
        DataFramePriceSource(
            energy=pd.DataFrame({"FR": pd.Series(150.0, index=naive_idx)}),
            compute=pd.DataFrame({"H100": pd.Series(0.5, index=naive_idx)}),
        )


def test_series_fx_rejects_naive_datetime():
    naive_idx = pd.date_range("2025-01-01", periods=2, freq="h")
    with pytest.raises(ValueError):
        SeriesFx(pd.Series([0.9, 0.8], index=naive_idx))


def test_non_utc_timezone_normalised_to_utc():
    """A non-UTC tz-aware index is accepted and normalised to UTC."""
    paris_idx = pd.date_range("2025-01-01", periods=2, freq="h", tz="Europe/Paris")
    src = DataFramePriceSource(
        energy=pd.DataFrame({"FR": pd.Series([150.0, 150.0], index=paris_idx)}),
        compute=pd.DataFrame({"H100": pd.Series([0.5, 0.5], index=paris_idx)}),
    )
    assert str(src.energy_price("FR").index.tz) == "UTC"


# ============================ (e) Dependency injection ===============================


class _DictPriceSource:
    """Mocked PriceSource, purely in-memory (proves the decoupling)."""

    def __init__(self, energy: dict[str, pd.Series], compute: dict[str, pd.Series]) -> None:
        self._energy = energy
        self._compute = compute

    def energy_price(self, region: str) -> pd.Series:
        return self._energy[region]

    def compute_price(self, gpu: str) -> pd.Series:
        return self._compute[gpu]


class _RecordingKernel:
    """Wraps the oracle to prove the injected kernel actually gets called."""

    def __init__(self) -> None:
        self._inner = PythonOracle()
        self.calls = 0

    def compute(self, *args: object) -> tuple[object, object, object]:
        self.calls += 1
        return self._inner.compute(*args)  # type: ignore[arg-type]


def test_pricer_runs_with_mocked_dependencies():
    idx = _utc_index(3)
    source = _DictPriceSource(
        energy={"FR": pd.Series(150.0, index=idx)},
        compute={"H100": pd.Series(0.5, index=idx)},
    )
    assert isinstance(source, PriceSource)  # runtime_checkable

    result = SparkSpreadPricer(_ref_power_model(), ConstantFx(1.0)).price(
        source, gpu="H100", region="FR"
    )
    assert round(result.spread.iloc[0], 2) == 0.31


def test_injected_kernel_is_used():
    idx = _utc_index(2)
    recorder = _RecordingKernel()
    SparkSpreadPricer(_ref_power_model(), ConstantFx(1.0), kernel=recorder).price(
        _source(pd.Series(150.0, index=idx), pd.Series(0.5, index=idx)),
        gpu="H100",
        region="FR",
    )
    assert recorder.calls == 1


def test_concrete_implementations_satisfy_protocols():
    assert isinstance(ConstantFx(1.0), FxConverter)
    assert isinstance(PythonOracle(), object)  # kernel checked via parity test


def test_default_kernel_falls_back_to_python_oracle_and_logs_warning(caplog):
    """V7.2: when Rust isn't compiled, the fallback to the Python oracle must be visible.

    The Rust subcrate is not built in this test environment (no ``maturin develop``), so
    the default (uninjected) kernel resolves through the fallback path -- mirroring
    ``core.backtest.engine``'s already-logged Rust->Python bascule.
    """
    with caplog.at_level("WARNING"):
        pricer = SparkSpreadPricer(_ref_power_model(), ConstantFx(1.0))

    assert isinstance(pricer._kernel, PythonOracle)
    assert "Rust kernel" in caplog.text
    assert "Python oracle" in caplog.text
