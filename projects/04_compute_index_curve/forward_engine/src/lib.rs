//! Moteur Monte-Carlo de la courbe forward compute (modèle de Schwartz un-facteur).
//!
//! Jambe perf (polyglotte) de P04 : simule de nombreux chemins du log-prix par
//! transition OU **exacte** entre échéances consécutives, puis renvoie le prix forward
//! (moyenne de `exp(x)`) à chaque échéance. L'oracle Python analytique sert de référence
//! de parité. Reproductible : seed explicite.

use pyo3::prelude::*;
use rand::distributions::Distribution;
use rand::rngs::StdRng;
use rand::SeedableRng;
use rand_distr::StandardNormal;

/// Simule la courbe forward aux `maturities` (en jours).
///
/// Renvoie les prix forward dans le même ordre que `maturities`. Le prix à l'échéance 0
/// vaut le spot (aucun pas simulé), garantissant la convergence.
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
        return Err(pyo3::exceptions::PyValueError::new_err("n_paths doit être > 0"));
    }

    let ln_theta = theta.ln();
    let mut x = vec![spot.ln(); n_paths];
    let mut rng = StdRng::seed_from_u64(seed);

    // Échéances triées/dédupliquées : on avance les chemins une seule fois dans le temps.
    let mut sorted = maturities.clone();
    sorted.sort_by(|a, b| a.partial_cmp(b).expect("échéance NaN interdite"));
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

    // Remappe vers l'ordre d'origine (les valeurs proviennent de la même liste source).
    let result = maturities
        .iter()
        .map(|&m| {
            sorted_fwd
                .iter()
                .find(|(mm, _)| *mm == m)
                .map(|(_, f)| *f)
                .expect("échéance absente du calcul")
        })
        .collect();
    Ok(result)
}

#[pymodule]
fn forward_engine(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(simulate_forward, m)?)?;
    Ok(())
}
