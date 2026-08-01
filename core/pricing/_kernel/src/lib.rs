//! Vectorised digital spark spread kernel, exposed to Python through pyo3.
//!
//! Implements strictly the same function as the Python oracle
//! (`core.pricing.oracle.PythonOracle`): `cost = power · pue · energy / 1000`,
//! `revenue = compute`, `spread = revenue − cost`, element-wise. The hot loop is
//! justified by the size of the historical grid (region × time × GPU).
//!
//! Bit-for-bit parity with the oracle is checked by `tests/test_pricer_parity.py`.

use numpy::{PyArray1, PyReadonlyArray1, ToPyArray};
use pyo3::prelude::*;

const KWH_PER_MWH: f64 = 1000.0;

/// Computes `(revenue, cost, spread)` element-wise.
#[pyfunction]
fn compute<'py>(
    py: Python<'py>,
    compute_eur_per_gpu_h: PyReadonlyArray1<'py, f64>,
    energy_eur_per_mwh: PyReadonlyArray1<'py, f64>,
    power_kw_per_gpu: PyReadonlyArray1<'py, f64>,
    pue: PyReadonlyArray1<'py, f64>,
) -> PyResult<(
    Bound<'py, PyArray1<f64>>,
    Bound<'py, PyArray1<f64>>,
    Bound<'py, PyArray1<f64>>,
)> {
    let compute = compute_eur_per_gpu_h.as_slice()?;
    let energy = energy_eur_per_mwh.as_slice()?;
    let power = power_kw_per_gpu.as_slice()?;
    let pue = pue.as_slice()?;

    let n = compute.len();
    let mut revenue = Vec::with_capacity(n);
    let mut cost = Vec::with_capacity(n);
    let mut spread = Vec::with_capacity(n);

    for i in 0..n {
        let rev = compute[i];
        let cst = power[i] * pue[i] * energy[i] / KWH_PER_MWH;
        revenue.push(rev);
        cost.push(cst);
        spread.push(rev - cst);
    }

    Ok((
        revenue.to_pyarray(py),
        cost.to_pyarray(py),
        spread.to_pyarray(py),
    ))
}

#[pymodule]
fn _kernel(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(compute, m)?)?;
    Ok(())
}
