"""Config centralisée du labo : chemins canoniques + lecture d'environnement.

Référencé par les rules. Aucune dépendance externe (pas de python-dotenv requis) :
les tokens vivent dans `.env` (recopié dans les worktrees via `.worktreeinclude`)
et sont lus depuis l'environnement du process.
"""

from __future__ import annotations

import os
from pathlib import Path

# Racine du dépôt (core/utils/config.py -> remonte de 2 niveaux).
REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"
SNAPSHOTS_DIR = DATA_DIR / "snapshots"
EXPERIMENTS_DIR = REPO_ROOT / "experiments"


def get_env(key: str, default: str | None = None, *, required: bool = False) -> str | None:
    """Lit une variable d'environnement. Lève si `required` et absente/vide."""
    value = os.environ.get(key, default)
    if required and not value:
        raise RuntimeError(
            f"Variable d'environnement requise absente : {key} "
            f"(la définir dans .env, recopié via .worktreeinclude)."
        )
    return value
