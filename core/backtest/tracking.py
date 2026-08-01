"""Reproducibility: MLflow logging of a backtest (params + metrics + git SHA + figure).

Composes :func:`core.utils.tracking.run` (which already logs params and the git SHA)
without modifying it, and adds the backtest-specific artefacts. Data files are
tracked as plain git objects, so the logged git SHA already pins the exact dataset
a run saw -- no separate data-version tag is needed. I/O is explicit and confined
to this module; the engine (``engine.py``) stays pure.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

import mlflow

from core.backtest.protocols import FloatArray
from core.utils import tracking as base_tracking


@contextmanager
def tracked_run(experiment: str, params: dict[str, Any]) -> Iterator[None]:
    """Open an MLflow run logging params and the git SHA (inherited).

    Examples
    --------
    >>> with tracked_run("p08_backtest_demo", params):  # doctest: +SKIP
    ...     log_metrics(result.metrics)
    ...     log_pnl_figure(cumulative_pnl(result.ledger.pnl))
    """
    with base_tracking.run(experiment, params):
        yield


def log_metrics(metrics: dict[str, float]) -> None:
    """Log the metrics mapping to the active MLflow run."""
    mlflow.log_metrics(metrics)


def log_pnl_figure(cumulative_pnl: FloatArray, artifact_file: str = "pnl_curve.html") -> None:
    """Log the cumulative PnL curve as an artefact of the active MLflow run."""
    import plotly.graph_objects as go

    figure = go.Figure(go.Scatter(y=cumulative_pnl, mode="lines", name="Cumulative PnL"))
    figure.update_layout(
        title="Cumulative PnL", xaxis_title="time step", yaxis_title="PnL (capital=1)"
    )
    mlflow.log_figure(figure, artifact_file)
