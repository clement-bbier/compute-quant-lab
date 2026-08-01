//! Monte-Carlo engine for the compute forward curve (1-factor Schwartz model).
//!
//! P04's performance leg (polyglot): simulates many log-price paths via an **exact**
//! OU transition between consecutive maturities, then returns the forward price
//! (mean of `exp(x)`) at each maturity. The analytical Python oracle serves as the
//! parity reference. Reproducible: explicit seed.

use pyo3::prelude::*;
use rand::distributions::Distribution;
use rand::rngs::StdRng;
use rand::SeedableRng;
use rand_distr::StandardNormal;

/// Simulates the forward curve at the given `maturities` (in days).
///
/// Returns the forward prices in the same order as `maturities`. The price at maturity 0
/// equals the spot (no step simulated), guaranteeing convergence.
#[pyfunction]
#[pyo3(signature = (spot, kappa, theta, sigma, maturities, n_paths, seed))]
fn simulate_forward(
    spot: f64,
    kappa: f64,
    theta: f64,
    sigma: f64,
    maturities: Vec<f64>,
    n_paths: usize,
    seed: u64,
) -> PyResult<Vec<f64>> {
    if n_paths == 0 {
        return Err(pyo3::exceptions::PyValueError::new_err("n_paths must be > 0"));
    }

    let ln_theta = theta.ln();
    let mut x = vec![spot.ln(); n_paths];
    let mut rng = StdRng::seed_from_u64(seed);

    // Sorted/deduplicated maturities: paths are advanced through time only once.
    let mut sorted = maturities.clone();
    sorted.sort_by(|a, b| a.partial_cmp(b).expect("NaN maturity not allowed"));
    sorted.dedup();

    let mut sorted_fwd: Vec<(f64, f64)> = Vec::with_capacity(sorted.len());
    let mut prev = 0.0_f64;
    for &m in &sorted {
        let step = m - prev;
        if step > 0.0 {
            let decay = (-kappa * step).exp();
            let var = (sigma * sigma / (2.0 * kappa)) * (1.0 - (-2.0 * kappa * step).exp());
            let sd = var.sqrt();
            for xi in x.iter_mut() {
                let z: f64 = StandardNormal.sample(&mut rng);
                *xi = decay * *xi + (1.0 - decay) * ln_theta + sd * z;
            }
        }
        let mean_exp = x.iter().map(|v| v.exp()).sum::<f64>() / (n_paths as f64);
        sorted_fwd.push((m, mean_exp));
        prev = m;
    }

    // Remap back to the original order (values come from the same source list).
    let result = maturities
        .iter()
        .map(|&m| {
            sorted_fwd
                .iter()
                .find(|(mm, _)| *mm == m)
                .map(|(_, f)| *f)
                .expect("maturity missing from computation")
        })
        .collect();
    Ok(result)
}

#[pymodule]
fn forward_engine(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(simulate_forward, m)?)?;
    Ok(())
}
