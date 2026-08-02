"""Standard lab logging. Never use `print` inside `core/` (rule python-quality)."""

from __future__ import annotations

import logging
import os

_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"

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


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Return a configured logger (single handler, no double-logging)."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(_FORMAT))
        logger.addHandler(handler)
        logger.setLevel(level)
        logger.propagate = False
    return logger


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
