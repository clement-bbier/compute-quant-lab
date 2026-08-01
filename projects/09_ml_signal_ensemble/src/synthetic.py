"""Deterministic synthetic data for the P09 PoC (strictly SIMULATED).

At PoC stage, we don't depend on ENTSO-E: we build a spark spread **priced by P01** whose
future direction carries a **modest but real** signal driven by an exogenous variable (gas
price), known with a publication lag via **P07**'s vintage mechanism. Goal: exercise the
whole pipeline (point-in-time features → purged-CV → P08 backtest) on a case where an
honest model finds a small edge — neither a perfect oracle nor pure noise.

Constraints honored:
* **strictly positive** spread (P08's PnL is expressed as a relative return
  ``price[t]/price[t-1]``, which would blow up near zero) — cf. `core.backtest.reference_loop`;
* ``simulated`` provenance **mandatory** (``forward-real-simulated`` rule);
* UTC timestamps, daily grid (P07's gas/HDD lags are expressed in days).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from core.features import DEFAULT_PUBLICATION_LAGS, from_lagged_series
from core.pricing import ServerSpec, energy_cost_per_gpu_hour, spark_spread_per_gpu_hour

#: Single generator seed (reproducibility).
SEED: int = 42

# --- Spread dynamics parameters (chosen for a MODEST edge, anti-illusion) -----------------
_MU: float = 2.3  # spread equilibrium level (EUR/GPU-h), realistic for H100
_KAPPA: float = 0.02  # mean-reversion speed (low -> little trivial signal)
_SIGMA: float = 0.06  # noise per step (dominates the signal -> modest accuracy expected)
_DELTA: float = 0.025  # weight of the exogenous (gas) lead on the next move
_FLOOR: float = 0.5  # safety floor: keeps the spread > 0 for the relative PnL


@dataclass(frozen=True)
class DataProvenance:
    """Real/simulated traceability. ``simulated`` is **mandatory** (lab rule)."""

    source: str
    simulated: bool  # no default value: a caller MUST state it explicitly


class InMemoryExogenousSource:
    """In-memory exogenous source (implements P07's `ExogenousSource`) serving vintages."""

    def __init__(self, vintages: dict[str, pd.DataFrame]) -> None:
        self._vintages = vintages

    def names(self) -> list[str]:
        return list(self._vintages)

    def vintages(self, name: str) -> pd.DataFrame:
        return self._vintages[name]


@dataclass(frozen=True)
class SyntheticDataset:
    """Generator output: P01 spread, P07 exogenous source, provenance."""

    spread: pd.Series
    exog_source: InMemoryExogenousSource
    provenance: DataProvenance


def generate(*, n_days: int = 2200, seed: int = SEED) -> SyntheticDataset:
    """Generate a deterministic synthetic dataset (P01 spread + lagged P07 exogenous data).

    The spread's move toward ``t`` is driven by gas **known at the previous decision
    point**: at decision instant ``d``, the ``gas_lag0`` feature (latest published vintage)
    therefore partially predicts the sign of the ``d -> d+1`` move. Weak edge (cf.
    ``_DELTA``/``_SIGMA``).
    """
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2019-01-01", periods=n_days, freq="D", tz="UTC")
    spec = ServerSpec()

    # Energy leg: bounded random walk (EUR/MWh).
    energy = np.clip(120.0 + np.cumsum(rng.standard_normal(n_days) * 3.0), 20.0, None)

    # Exogenous variables: gas (real lead) + HDD (exogenous noise, honest distractor).
    gas = np.clip(30.0 + np.cumsum(rng.standard_normal(n_days) * 1.0), 5.0, None)
    hdd = np.clip(rng.normal(10.0, 5.0, n_days), 0.0, None)
    gas_std = (gas - gas.mean()) / gas.std()

    # Spread = mean reversion + lagged exogenous lead + noise. spread[t] depends on gas
    # known at decision t-1 (gas_std[t-2]) -> gas_lag0 at decision d predicts d -> d+1.
    eps = rng.standard_normal(n_days)
    spread_latent = np.empty(n_days, dtype=np.float64)
    spread_latent[0] = _MU
    for t in range(1, n_days):
        driver = gas_std[t - 2] if t >= 2 else 0.0
        spread_latent[t] = (
            spread_latent[t - 1]
            + _KAPPA * (_MU - spread_latent[t - 1])
            + _DELTA * driver
            + _SIGMA * eps[t]
        )
    spread_latent = np.clip(spread_latent, _FLOOR, None)

    # Pricing BY P01: compute = energy cost + spread, then we re-price the spread
    # (round-trip) — we genuinely consume core.pricing, we don't reimplement it.
    energy_cost = np.array([energy_cost_per_gpu_hour(e, spec) for e in energy])
    compute_price = energy_cost + spread_latent
    spread = np.array(
        [spark_spread_per_gpu_hour(c, e, spec) for c, e in zip(compute_price, energy)]
    )
    spread_series = pd.Series(spread, index=idx, name="spark_spread")

    exog_source = InMemoryExogenousSource(
        {
            "gas_price": from_lagged_series(
                pd.Series(gas, index=idx), DEFAULT_PUBLICATION_LAGS["gas_price"]
            ),
            "hdd": from_lagged_series(pd.Series(hdd, index=idx), DEFAULT_PUBLICATION_LAGS["hdd"]),
        }
    )
    provenance = DataProvenance(source="synthetic_spark_spread_gas_lead", simulated=True)
    return SyntheticDataset(spread=spread_series, exog_source=exog_source, provenance=provenance)


__all__ = [
    "SEED",
    "DataProvenance",
    "InMemoryExogenousSource",
    "SyntheticDataset",
    "generate",
]
