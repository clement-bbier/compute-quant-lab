//! Noyau vectoriel du digital spark spread, exposé à Python via pyo3.
//!
//! Implémente strictement la même fonction que l'oracle Python
//! (`core.pricing.oracle.PythonOracle`) : `cost = power · pue · energy / 1000`,
//! `revenue = compute`, `spread = revenue − cost`, élément par élément. La boucle
//! chaude est justifiée par la taille de la grille historique (région × temps × GPU).
//!
//! La parité bit-à-bit avec l'oracle est vérifiée par `tests/test_pricer_parity.py`.

use numpy::{PyArray1, PyReadonlyArray1, ToPyArray};
use pyo3::prelude::*;

const KWH_PER_MWH: f64 = 1000.0;

/// Calcule `(revenu, coût, spread)` élément par élément.
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
