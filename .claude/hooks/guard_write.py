"""Garde-fou PreToolUse : refuse d'écrire dans les zones protégées du labo.

Remplace une version shell qui dépendait de `jq`. Sur une machine sans `jq`
— le cas par défaut sous Windows, alors que ce projet est Windows-first —
la substitution `$(jq ...)` échouait, la variable devenait vide, aucun motif
ne correspondait et le hook sortait en 0 : **le garde laissait passer
l'écriture**. Un garde-fou qui échoue en mode ouvert est pire que pas de
garde-fou, parce qu'il fait croire à une protection.

Ce script est donc *fail-closed* : toute anomalie (stdin illisible, JSON
invalide, champ absent, exception inattendue) bloque l'appel avec le code 2.
Il n'utilise que la bibliothèque standard, donc aucune dépendance à installer.

Conventions Claude Code :
- entrée : un objet JSON sur stdin, contenant `tool_input.file_path` ;
- sortie : code 0 = autorisé, code 2 = bloqué, message d'explication sur
  stderr (il est renvoyé au modèle pour qu'il corrige son geste).
"""

from __future__ import annotations

import json
import sys
from pathlib import PurePosixPath

#: Motifs interdits en écriture, avec le message rendu au modèle.
#: La clé est testée sur le chemin normalisé en séparateurs POSIX.
BLOCKED: tuple[tuple[str, str], ...] = (
    (
        "data/raw/",
        "BLOCKED: data/raw/ is immutable (point-in-time integrity). "
        "Write to data/interim/ instead.",
    ),
    (
        "data/snapshots/",
        "BLOCKED: data/snapshots/ is the collected raw history and is "
        "append-only via the collector. Never hand-edit it.",
    ),
)


def _normalize(raw: str) -> str:
    """Chemin en séparateurs POSIX, minuscules, pour un test insensible à l'OS."""
    return PurePosixPath(raw.replace("\\", "/")).as_posix().lower()


def _deny(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(2)


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:  # stdin vide, JSON tronqué, encodage cassé...
        _deny(f"BLOCKED: hook could not read its input ({exc!r}). Failing closed.")

    if not isinstance(payload, dict):
        _deny("BLOCKED: hook payload is not a JSON object. Failing closed.")

    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        _deny("BLOCKED: hook payload has no usable tool_input. Failing closed.")

    file_path = tool_input.get("file_path")
    if not isinstance(file_path, str) or not file_path.strip():
        # Certains outils n'écrivent pas de fichier : rien à garder, mais on
        # ne devine pas. Si le champ manque alors qu'on est sur Write/Edit,
        # c'est une anomalie -> blocage.
        _deny("BLOCKED: no file_path in tool_input. Failing closed.")

    normalized = _normalize(file_path)

    # Un .env ne doit jamais être écrit ni committé, où qu'il soit.
    name = normalized.rsplit("/", 1)[-1]
    if name == ".env" or name.startswith(".env."):
        if not name.endswith(".example"):
            _deny("BLOCKED: never write or commit a .env. Use .env.example.")

    for needle, message in BLOCKED:
        if needle in normalized:
            _deny(message)

    raise SystemExit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # filet de sécurité : jamais de passage silencieux
        print(f"BLOCKED: unexpected hook failure ({exc!r}). Failing closed.", file=sys.stderr)
        raise SystemExit(2) from exc
