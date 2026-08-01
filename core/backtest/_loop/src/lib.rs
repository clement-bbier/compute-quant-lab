//! Rust kernel for phase 2 of the backtest engine (PnL accumulation).
//!
//! Replicates **exactly** the Python oracle `core/backtest/reference_loop.py`
//! (same sequence of float64 operations, same order) to guarantee the
//! bit-for-bit parity tested by `test_parity`. This is the phase 2 **fast path**:
//! when this crate is not built, the engine falls back to that Python oracle, so
//! results are identical either way and only throughput differs.

use numpy::{IntoPyArray, PyArray1, PyReadonlyArray1};
use pyo3::prelude::*;

const BPS: f64 = 10_000.0;

/// Accumulates the point-in-time return series and counts the trades.
///
/// `return[t] = position[t-1] * (price[t]/price[t-1] - 1) - |Δpos| * cost_rate`.
#[pyfunction]
fn accumulate<'py>(
    py: Python<'py>,
    positions: PyReadonlyArray1<'py, f64>,
    prices: PyReadonlyArray1<'py, f64>,
    fees_bps: f64,
    slippage_bps: f64,
) -> PyResult<(Bound<'py, PyArray1<f64>>, usize)> {
    let pos = positions.as_slice()?;
    let prc = prices.as_slice()?;
    let n = pos.len();
    let cost_rate = (fees_bps + slippage_bps) / BPS;

    let mut returns = vec![0.0_f64; n];
    let mut prev_pos = 0.0_f64;
    let mut n_trades: usize = 0;

    for t in 0..n {
        let market_ret = if t == 0 { 0.0 } else { prc[t] / prc[t - 1] - 1.0 };
        let delta = pos[t] - prev_pos;
        if delta != 0.0 {
            n_trades += 1;
        }
        let trade_cost = delta.abs() * cost_rate;
        returns[t] = prev_pos * market_ret - trade_cost;
        prev_pos = pos[t];
    }

    Ok((returns.into_pyarray(py), n_trades))
}

#[pymodule]
fn backtest_loop(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(accumulate, m)?)?;
    Ok(())
}
