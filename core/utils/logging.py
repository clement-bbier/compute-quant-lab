"""Standard lab logging. Never use `print` inside `core/` (rule python-quality).

Library-safe by import: importing this module attaches no handler and calls
``logging.basicConfig`` nowhere. Entry points (runners, collectors, dashboards, the MCP
server) call :func:`configure_logging` once, explicitly, to get console output; anything
imported as a library (``core/``, project ``src/``) just calls :func:`get_logger` and
relies on the root handler an entry point installed. This is the standard "libraries
don't configure logging, applications do" split -- a library that adds its own handler at
import time causes duplicate lines the moment two such libraries are imported together.
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import overload

_FORMAT = "%(asctime)s %(levelname)s %(name)s [%(git_sha)s]%(provenance)s: %(message)s"

#: Env var names whose *values*, if present anywhere in a log message, must never reach a
#: log line in the clear. Not the full .env inventory -- only the secret-bearing ones (paths,
#: hosts and non-secret config are fine to log). Kept centralised here so every log site in
#: the ingestion tree (GPU providers, energy connectors) shares one list instead of each
#: call site enumerating its own subset and inevitably missing one.
SECRET_ENV_NAMES: tuple[str, ...] = (
    "ENTSOE_API_TOKEN",
    "GRIDSTATUS_API_KEY",
    "VASTAI_API_KEY",
    "RUNPOD_API_KEY",
    "PRIMEINTELLECT_API_KEY",
    "DATACRUNCH_CLIENT_ID",
    "DATACRUNCH_CLIENT_SECRET",
    "CUDO_API_KEY",
    "HYPERSTACK_API_KEY",
    "TENSORDOCK_API_KEY",
    "TENSORDOCK_API_AUTHORIZATION",
    "LAMBDA_API_KEY",
    "CRUSOE_ACCESS_KEY_ID",
    "CRUSOE_SECRET_KEY",
    "GENESISCLOUD_API_KEY",
    "SILICONDATA_API_TOKEN",
)

#: Max length of a sanitized message before truncation. A verbose HTTP client exception
#: (full request + response dump) is noise once secrets are stripped; this keeps logs
#: readable without needing the raw exception for anything a masked message can't answer.
_MAX_MESSAGE_LENGTH = 500

_REPO_ROOT = Path(__file__).resolve().parents[2]

_configured = False
_git_sha_cache: str | None = None


def _resolve_git_sha() -> str:
    """Resolve the short git SHA once per process; ``"unknown"`` is never returned silently.

    On failure the degraded value ``"unknown"`` is still used (log lines need a
    fixed-width field), but the failure itself is surfaced via ``logger.warning`` so it
    is visible instead of silently baked into every subsequent line.
    """
    global _git_sha_cache
    if _git_sha_cache is not None:
        return _git_sha_cache
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            text=True,
            cwd=_REPO_ROOT,
            stderr=subprocess.DEVNULL,
        ).strip()
        _git_sha_cache = sha
    except Exception as exc:  # noqa: BLE001 -- any failure (no git, no repo, detached) degrades the same way
        _git_sha_cache = "unknown"
        logging.getLogger(__name__).warning(
            "could not resolve git SHA for log context, using 'unknown': %s", exc
        )
    return _git_sha_cache


_original_record_factory = logging.getLogRecordFactory()


def _lab_record_factory(*args: object, **kwargs: object) -> logging.LogRecord:
    """``LogRecord`` factory stamping ``git_sha`` on every record, lab-wide.

    Installed via :func:`logging.setLogRecordFactory` rather than a ``Filter``: a filter
    only fires for the specific logger/handler it is attached to, so a *second* handler on
    the root logger installed independently of :func:`configure_logging` -- ``pytest``'s
    ``caplog`` being exactly that case -- would see raw records missing ``git_sha`` and
    crash formatting them (``KeyError`` in ``%``-style formatting). The record factory runs
    once at record-creation time, before any logger or handler is involved, so every
    consumer of the record sees the enriched field.

    ``provenance`` is deliberately NOT stamped here: it is supplied per-call via
    :class:`logging.LoggerAdapter`'s ``extra`` (see :func:`get_logger`), and ``extra``
    raises if a key it sets already exists on the record (``makeRecord`` treats that as an
    accidental overwrite). :data:`_FORMAT` uses ``_LabFormatter`` to tolerate its absence
    on plain (non-adapter) loggers instead.
    """
    record = _original_record_factory(*args, **kwargs)
    if not hasattr(record, "git_sha"):
        record.git_sha = _resolve_git_sha()
    return record


logging.setLogRecordFactory(_lab_record_factory)


class _LabFormatter(logging.Formatter):
    """Renders :data:`_FORMAT`, defaulting ``provenance`` to ``""`` when not adapter-supplied."""

    def format(self, record: logging.LogRecord) -> str:
        if not hasattr(record, "provenance"):
            record.provenance = ""
        return super().format(record)


def configure_logging(level: str | int | None = None) -> None:
    """Install the lab's root console handler -- call once, from an entry point only.

    Entry points are runners (``projects/*/src/run_*.py``, ``if __name__ == "__main__"``
    guards), collectors (``infra/collectors/*``), dashboards (``dashboard/app.py``) and the
    MCP server (``infra/mcp-servers/*/server.py``). Library code (``core/``, project
    ``src/`` modules imported by a runner) must never call this -- it should only ever call
    :func:`get_logger`.

    Idempotent: repeated calls reset the level but do not stack handlers.

    Parameters
    ----------
    level
        Root log level. Defaults to the ``LOG_LEVEL`` env var, itself defaulting to
        ``"INFO"``. Accepts either a level name (``"DEBUG"``) or a numeric level.
    """
    global _configured
    resolved = level if level is not None else os.environ.get("LOG_LEVEL", "INFO")
    root = logging.getLogger()
    if not _configured:
        handler = logging.StreamHandler()
        handler.setFormatter(_LabFormatter(_FORMAT))
        root.addHandler(handler)
        _configured = True
    root.setLevel(resolved)


@overload
def get_logger(name: str, *, simulated: None = None) -> logging.Logger: ...
@overload
def get_logger(name: str, *, simulated: bool) -> logging.LoggerAdapter[logging.Logger]: ...
def get_logger(
    name: str, *, simulated: bool | None = None
) -> logging.Logger | logging.LoggerAdapter[logging.Logger]:
    """Return the named logger, propagating to the root handler installed by an entry point.

    No handler is attached here and no level is set: attaching either at import time is
    exactly the library-configures-logging-at-import anti-pattern, which leaves a module
    silent under `import` (no handler until ``configure_logging`` or ``basicConfig`` ran)
    and duplicating lines whenever it is called more than once at different levels. Level
    and destination are decided once, by whichever entry point called
    :func:`configure_logging`; every ``get_logger`` caller just inherits it via normal
    propagation.

    Parameters
    ----------
    name
        Logger name (conventionally ``__name__`` or a short dotted label).
    simulated
        When the call site knows the real/simulated provenance of what it's about to log
        (rule ``forward-real-simulated``), pass it here to have every record tagged
        ``[real]``/``[simulated]``. Omit when the log site has no such notion (e.g. a
        generic infra message) -- the field is then blank, not a guessed default.

    Returns
    -------
    logging.Logger or logging.LoggerAdapter
        A plain logger if ``simulated`` is omitted; a :class:`logging.LoggerAdapter`
        stamping ``provenance`` on every record otherwise. Both accept the same
        ``.info()``/``.warning()``/... calls, so callers never need to branch on the type.
    """
    logger = logging.getLogger(name)
    if simulated is None:
        return logger
    provenance = " [simulated]" if simulated else " [real]"
    return logging.LoggerAdapter(logger, {"provenance": provenance})


def sanitize_for_log(message: str) -> str:
    """Mask configured secret values and truncate before a message reaches a log line.

    ``str(exc)`` on an HTTP client error (e.g. ``requests`` on a 4xx) routinely echoes the
    failing request -- headers, URL, sometimes the body -- which can include an API key
    passed as a header or query param. Iterates :data:`SECRET_ENV_NAMES`, replacing any
    *currently configured* value found in ``message`` with ``"***"``, then truncates.

    Reads live from ``os.environ`` rather than accepting a values argument, so a call site
    cannot forget to pass the relevant name -- the full known list is always checked.
    """
    sanitized = message
    for name in SECRET_ENV_NAMES:
        value = os.environ.get(name)
        if value:
            sanitized = sanitized.replace(value, "***")
    if len(sanitized) > _MAX_MESSAGE_LENGTH:
        sanitized = sanitized[:_MAX_MESSAGE_LENGTH] + "... [truncated]"
    return sanitized
