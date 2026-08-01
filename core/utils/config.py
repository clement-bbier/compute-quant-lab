"""Centralised lab config: canonical paths + environment lookup.

Referenced by the rules. No external dependency (python-dotenv is not required):
tokens live in `.env` (copied into worktrees via `.worktreeinclude`) and are read
from the process environment.
"""

from __future__ import annotations

import os
from pathlib import Path

# Repository root (core/utils/config.py -> two levels up).
REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"
SNAPSHOTS_DIR = DATA_DIR / "snapshots"
EXPERIMENTS_DIR = REPO_ROOT / "experiments"


def get_env(key: str, default: str | None = None, *, required: bool = False) -> str | None:
    """Read an environment variable. Raise if `required` and missing/empty."""
    value = os.environ.get(key, default)
    if required and not value:
        raise RuntimeError(
            f"required environment variable {key} must be set "
            f"(define it in .env, copied via .worktreeinclude)."
        )
    return value
