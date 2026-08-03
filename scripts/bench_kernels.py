"""Micro-benchmark: Python oracle vs. Rust kernel, on realistic sizes, for the 3 crates.

Ad hoc, not wired into CI: run manually after ``make kernels`` to get a sober one-line
number per crate for the README. Answers "is the Rust path actually faster" with a
measurement instead of an assumption.
"""

from __future__ import annotations

import statistics
import sys
import time
from pathlib import Path
from typing import Callable

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent / "projects/04_compute_index_curve/src"))

N_REPEATS = 7


def _time(fn: Callable[[], object]) -> float:
    """Median wall-clock seconds over `N_REPEATS` calls (one warmup, discarded)."""
    fn()
    samples = []
    for _ in range(N_REPEATS):
        t0 = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - t0)
    return statistics.median(samples)


def bench_pricing_kernel(n: int = 100_000) -> tuple[float, float]:
    from core.pricing.oracle import PythonOracle
    from core.pricing.pricer import RustKernel

    rng = np.random.default_rng(0)
    compute = rng.uniform(1.0, 5.0, n)
    energy = rng.uniform(20.0, 120.0, n)
    power = np.full(n, 0.7)
    pue = np.full(n, 1.3)

    py = PythonOracle()
    rs = RustKernel()
    t_py = _time(lambda: py.compute(compute, energy, power, pue))
    t_rs = _time(lambda: rs.compute(compute, energy, power, pue))
    return t_py, t_rs


def bench_backtest_loop(n: int = 100_000) -> tuple[float, float]:
    import backtest_loop

    from core.backtest.reference_loop import accumulate

    rng = np.random.default_rng(0)
    prices = np.clip(100.0 + np.cumsum(rng.standard_normal(n)), 1.0, None).astype(np.float64)
    positions = rng.choice([-1.0, 0.0, 1.0], size=n).astype(np.float64)

    t_py = _time(lambda: accumulate(positions, prices, 10.0, 5.0))
    t_rs = _time(lambda: backtest_loop.accumulate(positions, prices, 10.0, 5.0))
    return t_py, t_rs


def bench_forward_engine(n_paths: int = 100_000) -> tuple[float, float]:
    import forward_engine

    from forward.oracle import PythonMonteCarloForward
    from forward.models import SchwartzParams

    params = SchwartzParams(kappa=1.5, theta=np.log(2.5), sigma=0.4)
    maturities = [30.0, 60.0, 90.0, 180.0, 365.0]
    spot = 2.5

    py = PythonMonteCarloForward(n_paths=n_paths, seed=0)
    t_py = _time(lambda: py.simulate(spot, params, maturities))
    t_rs = _time(
        lambda: forward_engine.simulate_forward(
            spot, params.kappa, params.theta, params.sigma, maturities, n_paths, 0
        )
    )
    return t_py, t_rs


def main() -> None:
    results = {
        "pricing kernel (_kernel, n=100k rows)": bench_pricing_kernel(),
        "backtest loop (_loop, n=100k periods)": bench_backtest_loop(),
        "forward engine (Monte Carlo, 100k paths)": bench_forward_engine(),
    }
    print(f"{'crate':45s} {'python (s)':>12s} {'rust (s)':>12s} {'speedup':>10s}")
    for label, (t_py, t_rs) in results.items():
        speedup = t_py / t_rs if t_rs > 0 else float("inf")
        print(f"{label:45s} {t_py:12.4f} {t_rs:12.4f} {speedup:9.1f}x")


if __name__ == "__main__":
    main()
