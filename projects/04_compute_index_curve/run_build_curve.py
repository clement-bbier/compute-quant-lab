"""Entrée exécutable : construit et logue une courbe forward compute SIMULÉE.

Usage :
    uv run python projects/04_compute_index_curve/run_build_curve.py

Pipeline : (1) spot courant via l'indice si des snapshots réels existent
(``data/snapshots/``), sinon spot de démonstration ; (2) calibration des paramètres de
Schwartz sur l'historique du log-spot ; (3) simulation de la courbe forward (moteur Rust
si buildé, sinon MC Python) ; (4) **run MLflow** loggué (params + SHA git).

⚠️ La courbe produite est TOUJOURS ``simulated=True`` : les futures compute CME (settlement
sur l'indice Silicon Data SDH100RT) ne sont pas listés. Tant que la série de snapshots est
mince, l'historique de calibration ci-dessous est synthétique (clairement étiqueté) ; il
suffira de le remplacer par la série réelle de l'indice une fois la collecte accumulée.
"""

from __future__ import annotations

import logging
import math
import os
import sys
from pathlib import Path

# Convention labo : tracking MLflow fichier local. MLflow 2026 exige cet opt-in.
os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")
_ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("MLFLOW_TRACKING_URI", (_ROOT / "experiments" / "mlruns").as_uri())
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from core.ingestion import CsvSnapshotStore, InsufficientDataError, build_spot_index  # noqa: E402
from forward.build_curve import build_forward_curve  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("run_build_curve")

SNAPSHOT_DIR = _ROOT / "data" / "snapshots"
GPU_MODEL = "H100"
MATURITIES = [0.0, 7.0, 30.0, 90.0, 180.0, 360.0]


def _current_spot() -> float:
    """Spot courant via l'indice sur les snapshots réels, sinon valeur de démonstration."""
    snapshots = CsvSnapshotStore(SNAPSHOT_DIR).load()
    if snapshots:
        try:
            now = max(s.snapshotted_at for s in snapshots)
            point = build_spot_index(snapshots, now, GPU_MODEL)
            logger.info("Spot réel de l'indice : %.4f $/GPU·h (%s)", point.price_usd_per_hour, point.method)
            return point.price_usd_per_hour
        except InsufficientDataError:
            logger.warning("Snapshots présents mais insuffisants : spot de démonstration.")
    return 2.30


def _demo_log_history(spot: float, n: int = 180, seed: int = 7) -> list[float]:
    """Historique synthétique mean-reverting du log-spot (placeholder, étiqueté démo)."""
    import numpy as np

    rng = np.random.default_rng(seed)
    kappa, sigma, dt_days = 0.05, 0.06, 1.0
    ln_theta = math.log(spot)
    decay = math.exp(-kappa * dt_days)
    sd = math.sqrt((sigma**2 / (2 * kappa)) * (1 - math.exp(-2 * kappa * dt_days)))
    x = [ln_theta]
    for _ in range(n - 1):
        x.append(decay * x[-1] + (1 - decay) * ln_theta + sd * float(rng.standard_normal()))
    return x


def main() -> None:
    spot = _current_spot()
    history = _demo_log_history(spot)
    curve = build_forward_curve(history, spot=spot, maturities_days=MATURITIES)

    logger.info("Courbe forward SIMULÉE (%s, seed=%s, n_paths=%s) :", curve.model_name, curve.seed, curve.n_paths)
    for point in curve.points:
        logger.info("  τ=%6.1f j -> %.4f $/GPU·h", point.maturity_days, point.forward_price)
    logger.info("Run loggué sous %s (experiment 'compute_forward_curve').", os.environ["MLFLOW_TRACKING_URI"])


if __name__ == "__main__":
    main()
