"""Hook PostToolUse : formate le fichier Python qui vient d'être écrit.

Contrairement à `guard_write.py`, ce hook est **fail-open et volontairement
silencieux** : il ne protège rien, il rend service. Si `ruff` est absent ou
échoue, l'édition reste valide et la session continue — la CI et pre-commit
restent les filets de sécurité sur la qualité.

Écrit en Python standard (pas de `jq`) pour fonctionner sous Windows.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        file_path = payload["tool_input"]["file_path"]
    except Exception:
        return 0  # rien d'exploitable : on ne dérange pas la session

    if not isinstance(file_path, str) or not file_path.endswith(".py"):
        return 0

    ruff = shutil.which("ruff")
    if ruff is None:
        return 0

    for args in (["format", file_path], ["check", "--fix", file_path]):
        try:
            subprocess.run(
                [ruff, *args],
                capture_output=True,
                timeout=30,
                check=False,
            )
        except Exception:
            return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
