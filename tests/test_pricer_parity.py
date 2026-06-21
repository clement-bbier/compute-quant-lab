"""(d) Parité Rust ↔ Python du noyau de spread.

Le noyau Rust (`core.pricing._kernel`) est un subcrate maturin optionnel. Tant
qu'il n'est pas compilé (``maturin develop``), ce test est *skippé* : le PoC
reste 100 % vert en pur Python, le Rust est additif.
"""

from __future__ import annotations

import numpy as np
import pytest

from core.pricing import PythonOracle

try:
    from core.pricing.pricer import RustKernel

    _rust = RustKernel()
except Exception:  # pragma: no cover - dépend de la compilation du subcrate
    _rust = None


@pytest.mark.skipif(_rust is None, reason="noyau Rust non compilé (maturin develop)")
def test_rust_matches_python_oracle():
    rng = np.random.default_rng(42)
    n = 10_000
    compute_eur = rng.uniform(0.1, 5.0, n)
    energy = rng.uniform(10.0, 800.0, n)
    power = rng.uniform(0.3, 1.0, n)
    pue = rng.uniform(1.0, 2.0, n)

    oracle = PythonOracle()
    rev_p, cost_p, spread_p = oracle.compute(compute_eur, energy, power, pue)
    rev_r, cost_r, spread_r = _rust.compute(compute_eur, energy, power, pue)  # type: ignore[union-attr]

    assert np.allclose(rev_p, rev_r)
    assert np.allclose(cost_p, cost_r)
    assert np.allclose(spread_p, spread_r)
