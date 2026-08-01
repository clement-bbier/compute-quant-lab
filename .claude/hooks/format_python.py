"""PostToolUse hook: formats the Python file that was just written.

Unlike `guard_write.py`, this hook is **fail-open and deliberately
silent**: it protects nothing, it is a convenience. If `ruff` is absent or
fails, the edit stays valid and the session continues — CI and pre-commit
remain the safety nets on quality.

Written in standard Python (no `jq`) to work on Windows.
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
        return 0  # nothing usable: don't disturb the session

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
