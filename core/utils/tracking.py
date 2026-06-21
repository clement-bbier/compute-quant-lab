"""Wrapper léger autour de MLflow — tracking local, sans serveur.

Garantit que chaque run loggue le minimum vital pour la reproductibilité :
params, métriques, SHA git, et (à brancher) la version DVC des données.
"""

from __future__ import annotations

import subprocess
from contextlib import contextmanager
from typing import Any, Iterator

import mlflow


def _git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


@contextmanager
def run(experiment: str, params: dict[str, Any]) -> Iterator[None]:
    """Ouvre un run MLflow en loggant params + SHA git automatiquement.

    Usage :
        with run("spark_spread_backtest", {"z_entry": 2.0}):
            ... ; mlflow.log_metric("sharpe", s)
    """
    mlflow.set_experiment(experiment)
    with mlflow.start_run():
        mlflow.log_params(params)
        mlflow.set_tag("git_sha", _git_sha())
        yield
