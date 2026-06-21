"""Wrapper léger autour de MLflow — tracking local, sans serveur.

Garantit que chaque run loggue le minimum vital pour la reproductibilité :
params, métriques, SHA git et version DVC des données.

Convergence : centralise deux décisions du labo qui étaient des stopgaps locaux
dans les projets P01/P08 —
  - le store MLflow vit sous `experiments/mlruns` (convention CLAUDE.md §4) ;
  - MLflow >= 3 met le file store en « maintenance mode » → opt-out explicite.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import mlflow

REPO_ROOT = Path(__file__).resolve().parents[2]

# MLflow >= 3 : le file store lève sans cet opt-out. Centralisé ici pour tout le labo.
os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")
# Store local unique sous experiments/ (gitignoré), sauf override explicite.
if not os.environ.get("MLFLOW_TRACKING_URI"):
    mlflow.set_tracking_uri((REPO_ROOT / "experiments" / "mlruns").as_uri())


def _git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def _dvc_version() -> str:
    """Empreinte déterministe des données versionnées DVC (pointeurs `*.dvc` + lock).

    Permet de rejouer un run sur exactement la même version de données.
    """
    parts: list[Path] = []
    data_dir = REPO_ROOT / "data"
    if data_dir.exists():
        parts.extend(sorted(data_dir.rglob("*.dvc")))
    lock = REPO_ROOT / "dvc.lock"
    if lock.exists():
        parts.append(lock)
    if not parts:
        return "none"
    digest = hashlib.sha1()
    for path in parts:
        digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


@contextmanager
def run(experiment: str, params: dict[str, Any]) -> Iterator[None]:
    """Ouvre un run MLflow en loggant params + SHA git + version DVC automatiquement.

    Usage :
        with run("spark_spread_backtest", {"z_entry": 2.0}):
            ... ; mlflow.log_metric("sharpe", s)
    """
    mlflow.set_experiment(experiment)
    with mlflow.start_run():
        mlflow.log_params(params)
        mlflow.set_tag("git_sha", _git_sha())
        mlflow.set_tag("dvc_version", _dvc_version())
        yield
