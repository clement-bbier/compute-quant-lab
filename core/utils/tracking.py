"""Thin wrapper around MLflow -- local tracking, no server.

Guarantees that every run logs the minimum needed for reproducibility: params,
metrics and the git SHA. Data files are tracked as plain git objects, so that SHA
already pins the exact dataset a run saw.

Centralises two lab-wide decisions that used to be local stopgaps in projects
P01/P08:

- the MLflow store lives under ``experiments/mlruns`` (CLAUDE.md section 4);
- MLflow >= 3 puts the file store in "maintenance mode", so it needs an explicit
  opt-out.

Both are applied by :func:`init_tracking`, which callers invoke explicitly.
Importing this module has no side effect on process state: it never mutates the
environment nor sets a global tracking URI at import time. :func:`run` calls
:func:`init_tracking` on first use, so runners get the lab defaults for free.
"""

from __future__ import annotations

import os
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import mlflow

from core.utils.logging import get_logger

logger = get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Default local MLflow store, relative to the repository root (git-ignored).
DEFAULT_STORE = REPO_ROOT / "experiments" / "mlruns"

_initialised = False


def init_tracking(store: Path | None = None, *, force: bool = False) -> None:
    """Apply the lab's MLflow defaults: file-store opt-out and local store URI.

    Idempotent: repeated calls are no-ops unless ``force`` is set. An explicit
    ``MLFLOW_TRACKING_URI`` in the environment always wins, so a runner can point
    at another store without editing code.

    Parameters
    ----------
    store
        Directory backing the local file store. Defaults to :data:`DEFAULT_STORE`.
    force
        Re-apply the settings even if this function already ran.
    """
    global _initialised
    if _initialised and not force:
        return
    # MLflow >= 3 raises on a file store without this opt-out.
    os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")
    if not os.environ.get("MLFLOW_TRACKING_URI"):
        mlflow.set_tracking_uri((store or DEFAULT_STORE).as_uri())
    _initialised = True


def _git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception as exc:  # noqa: BLE001 -- any failure (no git, no repo) degrades the same way
        logger.warning("could not resolve git SHA for MLflow tagging, using 'unknown': %s", exc)
        return "unknown"


@contextmanager
def run(experiment: str, params: dict[str, Any]) -> Iterator[None]:
    """Open an MLflow run, logging params and the git SHA automatically.

    Examples
    --------
    >>> with run("spark_spread_backtest", {"z_entry": 2.0}):  # doctest: +SKIP
    ...     mlflow.log_metric("sharpe", s)
    """
    init_tracking()
    mlflow.set_experiment(experiment)
    with mlflow.start_run():
        mlflow.log_params(params)
        mlflow.set_tag("git_sha", _git_sha())
        yield
