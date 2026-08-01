"""(d) Rust <-> Python parity of the spread kernel.

The Rust kernel (`core.pricing._kernel`) is an optional maturin subcrate. As
long as it isn't compiled (``maturin develop``), this test is *skipped*: the PoC
stays 100% green in pure Python, Rust is additive.
"""

from __future__ import annotations

import numpy as np
import pytest

from core.pricing import PythonOracle

try:
    from core.pricing.pricer import RustKernel

    _rust = RustKernel()
except Exception:  # pragma: no cover - depends on the subcrate being compiled
    _rust = None


@pytest.mark.skipif(_rust is None, reason="Rust kernel not compiled (maturin develop)")
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
