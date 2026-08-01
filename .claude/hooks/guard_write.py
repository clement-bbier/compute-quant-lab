"""PreToolUse guardrail: refuses to write into the lab's protected zones.

Replaces a shell version that depended on `jq`. On a machine without `jq`
— the default case on Windows, and this project is Windows-first — the
`$(jq ...)` substitution failed, the variable became empty, no pattern
matched, and the hook exited 0: **the guard let the write through**. A
guardrail that fails open is worse than no guardrail at all, because it
gives a false sense of protection.

This script is therefore *fail-closed*: any anomaly (unreadable stdin,
invalid JSON, missing field, unexpected exception) blocks the call with
exit code 2. It only uses the standard library, so there is no dependency to install.

Claude Code conventions:
- input: a JSON object on stdin, containing `tool_input.file_path`;
- output: exit code 0 = allowed, exit code 2 = blocked, explanation message
  on stderr (it is returned to the model so it can correct its action).
"""

from __future__ import annotations

import json
import sys
from pathlib import PurePosixPath

#: Patterns forbidden on write, with the message returned to the model.
#: The key is tested against the path normalized to POSIX separators.
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
    """Path in POSIX separators, lowercase, for an OS-insensitive test."""
    return PurePosixPath(raw.replace("\\", "/")).as_posix().lower()


def _deny(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(2)


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:  # empty stdin, truncated JSON, broken encoding...
        _deny(f"BLOCKED: hook could not read its input ({exc!r}). Failing closed.")

    if not isinstance(payload, dict):
        _deny("BLOCKED: hook payload is not a JSON object. Failing closed.")

    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        _deny("BLOCKED: hook payload has no usable tool_input. Failing closed.")

    file_path = tool_input.get("file_path")
    if not isinstance(file_path, str) or not file_path.strip():
        # Some tools don't write a file: nothing to guard, but we don't
        # guess. If the field is missing while we're on Write/Edit, that
        # is an anomaly -> block.
        _deny("BLOCKED: no file_path in tool_input. Failing closed.")

    normalized = _normalize(file_path)

    # A .env must never be written or committed, wherever it is.
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
    except Exception as exc:  # safety net: never fail silently
        print(f"BLOCKED: unexpected hook failure ({exc!r}). Failing closed.", file=sys.stderr)
        raise SystemExit(2) from exc
