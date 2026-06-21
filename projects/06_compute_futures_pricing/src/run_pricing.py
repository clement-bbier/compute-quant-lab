"""Démo P06 : pricing THÉORIQUE de futures compute, loggué MLflow.

Pipeline reproductible (params connus, oracle analytique déterministe) :
  1. charge le spot compute **réel** (``core.ingestion``) ; repli **loggué** sur une
     hypothèse si aucun snapshot n'est disponible (jamais un échec silencieux) ;
  2. construit la courbe forward **SIMULÉE** de P04 (Schwartz analytique) ;
  3. price la grille d'échéances via DEUX sources de forward — cost-of-carry exogène
     et adapter P04 — et calcule la base ``F − S`` + le convenience yield implicite ;
  4. loggue params + métriques dans MLflow (``core.utils.tracking.run``) ;
  5. écrit ``results/futures_pricing_summary.json`` avec l'avertissement réel/simulé.

⚠️ Tous les prix sont THÉORIQUES/SIMULÉS : les futures compute (settlement SDH100RT)
ne sont pas listés. Ne jamais présenter ces chiffres comme un marché observé.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

# MLflow >= 3 met le file store en « maintenance mode » : opt-out explicite (avant import).
os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")

import mlflow  # noqa: E402 - après l'opt-out file-store ci-dessus

REPO_ROOT = Path(__file__).resolve().parents[3]
_P06_SRC = Path(__file__).resolve().parent
_P04_SRC = REPO_ROOT / "projects" / "04_compute_index_curve" / "src"
for _path in (str(_P06_SRC), str(_P04_SRC)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from core.pricing.derivatives import (  # noqa: E402
    DEFAULT_RISK_FREE_RATE,
    CarryFuturesPricer,
    CostOfCarryModel,
    FuturesQuote,
)
from core.utils.tracking import run  # noqa: E402
from forward.models import SchwartzParams  # noqa: E402
from p04_forward_adapter import DAYS_PER_YEAR, P04ForwardAdapter  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("run_pricing")

RESULTS = Path(__file__).resolve().parents[1] / "results"

GPU = "H100"
RATE = DEFAULT_RISK_FREE_RATE  # taux de financement annualisé (hypothèse)
CONVENIENCE_YIELD = 0.01  # convenience yield exogène (hypothèse PoC, non observable)
MATURITIES_DAYS = [30.0, 90.0, 180.0, 360.0]
# Courbe forward Schwartz : paramètres d'hypothèse (à défaut de calibration réelle ici).
SCHWARTZ = SchwartzParams(kappa=0.05, theta=2.5, sigma=0.3)
ASSUMED_SPOT_USD = 2.50  # repli documenté si aucun snapshot réel n'est disponible

DISCLAIMER = (
    "THÉORIQUE/SIMULÉ — les futures compute (settlement SDH100RT) ne sont pas listés. "
    "La forward provient d'un modèle (Schwartz/carry), jamais d'un marché observé."
)


def load_real_spot() -> tuple[float, str]:
    """Spot compute réel via ``core.ingestion`` ; repli **loggué** sinon.

    Returns
    -------
    tuple[float, str]
        ``(spot_usd_per_gpu_h, source)`` où ``source`` distingue le réel du repli.
    """
    try:
        from core.ingestion import CsvSnapshotStore, build_spot_index
        from core.utils.config import SNAPSHOTS_DIR

        snapshots = CsvSnapshotStore(SNAPSHOTS_DIR).load()
        if not snapshots:
            raise FileNotFoundError(f"aucun snapshot sous {SNAPSHOTS_DIR}")
        point = build_spot_index(snapshots, dt.datetime.now(dt.timezone.utc), GPU)
        log.info(
            "Spot réel %s = %.4f $/GPU·h (%d venues)",
            GPU,
            point.price_usd_per_hour,
            point.n_sources,
        )
        return point.price_usd_per_hour, "real:compute_index"
    except Exception as exc:  # noqa: BLE001 - repli documenté, jamais silencieux
        log.warning(
            "Spot réel indisponible (%s) — repli sur hypothèse %.2f $/GPU·h", exc, ASSUMED_SPOT_USD
        )
        return ASSUMED_SPOT_USD, "assumed_fallback"


def _row(tau_days: float, carry: FuturesQuote, p04: FuturesQuote) -> dict[str, float]:
    return {
        "maturity_days": tau_days,
        "tau_years": carry.maturity_years,
        "carry_forward": carry.forward,
        "carry_basis": carry.basis,
        "carry_d_forward_d_tau": carry.sensitivities.d_forward_d_tau,
        "p04_forward": p04.forward,
        "p04_basis": p04.basis,
        "p04_implied_convenience_yield": p04.convenience_yield,
    }


def main() -> None:
    spot, spot_source = load_real_spot()

    carry_pricer = CarryFuturesPricer(
        CostOfCarryModel(rate=RATE, convenience_yield=CONVENIENCE_YIELD), rate=RATE
    )
    p04_pricer = CarryFuturesPricer(P04ForwardAdapter(SCHWARTZ), rate=RATE)

    term_structure = [
        _row(
            tau_days,
            carry_pricer.price(spot, tau_days / DAYS_PER_YEAR),
            p04_pricer.price(spot, tau_days / DAYS_PER_YEAR),
        )
        for tau_days in MATURITIES_DAYS
    ]

    params: dict[str, Any] = {
        "gpu": GPU,
        "spot_usd_per_gpu_h": spot,
        "spot_source": spot_source,
        "rate_annual": RATE,
        "carry_convenience_yield": CONVENIENCE_YIELD,
        "forward_model": "schwartz_analytic+cost_of_carry",
        "schwartz_kappa": SCHWARTZ.kappa,
        "schwartz_theta": SCHWARTZ.theta,
        "schwartz_sigma": SCHWARTZ.sigma,
        "maturities_days": ",".join(str(int(m)) for m in MATURITIES_DAYS),
        "simulated": True,
    }

    with run("p06_compute_futures_pricing", params):
        for row in term_structure:
            d = int(row["maturity_days"])
            mlflow.log_metric(f"carry_basis_{d}d", row["carry_basis"])
            mlflow.log_metric(f"p04_basis_{d}d", row["p04_basis"])
            mlflow.log_metric(f"p04_implied_yield_{d}d", row["p04_implied_convenience_yield"])

    RESULTS.mkdir(parents=True, exist_ok=True)
    summary = {
        "disclaimer": DISCLAIMER,
        "simulated": True,
        "params": params,
        "term_structure": term_structure,
    }
    (RESULTS / "futures_pricing_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    log.info(
        "Spot=%.4f $/GPU·h (%s) | base P04 360j=%.4f | yield impl. 360j=%.4f",
        spot,
        spot_source,
        term_structure[-1]["p04_basis"],
        term_structure[-1]["p04_implied_convenience_yield"],
    )
    log.info("Résumé écrit : %s — %s", RESULTS / "futures_pricing_summary.json", DISCLAIMER)


if __name__ == "__main__":
    main()
