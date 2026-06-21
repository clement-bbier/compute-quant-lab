"""Reproductibilité : logging MLflow d'un backtest (params + métriques + SHA + DVC + figure).

Compose `core.utils.tracking.run` (qui logge déjà params + SHA git) sans le modifier,
et ajoute la **version DVC** des données — rendant exécutable la convention du labo
« tout backtest loggué MLflow + SHA git + version DVC ». L'I/O est explicite et isolé
ici ; le moteur (`engine.py`) reste pur.
"""

from __future__ import annotations

import hashlib
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import mlflow

from core.backtest.protocols import FloatArray
from core.utils import tracking as base_tracking


def dvc_version() -> str:
    """Empreinte de la version des données DVC (best-effort, jamais bloquant).

    Hash court de `dvc.lock` s'il existe, sinon `"no-dvc-data"` quand rien n'est
    encore traqué (cas actuel du dépôt). Garantit qu'un run logge toujours *une*
    version DVC, même vide.
    """
    lock = Path("dvc.lock")
    if lock.exists():
        return hashlib.sha256(lock.read_bytes()).hexdigest()[:12]
    return "no-dvc-data"


@contextmanager
def tracked_run(experiment: str, params: dict[str, Any]) -> Iterator[None]:
    """Run MLflow loggant params + SHA git (hérité) + version DVC.

    Usage :
        with tracked_run("p08_backtest_demo", params):
            log_metrics(result.metrics)
            log_pnl_figure(cumulative_pnl(result.ledger.pnl))
    """
    with base_tracking.run(experiment, params):
        mlflow.set_tag("dvc_version", dvc_version())
        yield


def log_metrics(metrics: dict[str, float]) -> None:
    """Logge le dictionnaire de métriques dans le run MLflow actif."""
    mlflow.log_metrics(metrics)


def log_pnl_figure(cumulative_pnl: FloatArray, artifact_file: str = "pnl_curve.html") -> None:
    """Logge la courbe de PnL cumulé comme artefact du run MLflow actif."""
    import plotly.graph_objects as go

    figure = go.Figure(go.Scatter(y=cumulative_pnl, mode="lines", name="PnL cumulé"))
    figure.update_layout(
        title="PnL cumulé", xaxis_title="pas de temps", yaxis_title="PnL (capital=1)"
    )
    mlflow.log_figure(figure, artifact_file)
