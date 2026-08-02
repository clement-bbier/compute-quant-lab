"""Shared HTTP call policy: one timeout, one bounded retry (budget-zero).

Every network call in the lab (GPU marketplace providers, GridStatus/ERCOT transports)
should share the same timeout and the same retry rule instead of each call site
re-deciding it. The rule is deliberately narrow: retrying a 4xx burns a free-tier quota
for nothing (the request will fail identically every time), so only failures that can
plausibly succeed on a second attempt -- 5xx, timeouts, connection errors -- are retried.

``call_with_retry`` wraps any zero-argument callable (typically a ``requests.get``/
``.post`` invocation via a lambda or ``functools.partial``); it does not import
``requests`` itself so it stays usable for non-``requests`` transports (e.g. the
``gridstatusio`` client) that raise their own exception types on top of the same
underlying causes.
"""

from __future__ import annotations

import time
from typing import Callable, TypeVar

import requests

from core.utils.logging import get_logger, sanitize_for_log

logger = get_logger(__name__)

#: Single source of truth for HTTP call timeouts (seconds). Applies to every provider
#: and to GridStatus calls.
DEFAULT_TIMEOUT_S: float = 30.0

#: Maximum number of *retry* attempts after the first try (2 retries = 3 attempts total).
MAX_RETRIES: int = 2

#: Backoff between retries (seconds) -- short and fixed: budget-zero means no exponential
#: ladder is worth the extra latency for a free-tier quota that is precious either way.
_RETRY_BACKOFF_S: float = 1.0

_T = TypeVar("_T")


def is_retryable_http_error(exc: BaseException) -> bool:
    """Whether ``exc`` is worth a retry: 5xx, timeout, or connection failure.

    A 4xx (``requests.HTTPError`` with a 4xx response) is explicitly excluded: retrying
    an unauthorized/malformed request cannot succeed and only spends quota. Any exception
    type outside ``requests``' own hierarchy (a programming error, a parsing bug) is also
    not retryable -- retrying would mask it instead of surfacing it.
    """
    if isinstance(exc, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)):
        return True
    if isinstance(exc, requests.exceptions.HTTPError):
        response = exc.response
        return response is not None and response.status_code >= 500
    return False


def call_with_retry(
    fn: Callable[[], _T],
    *,
    venue: str,
    max_retries: int = MAX_RETRIES,
    backoff_s: float = _RETRY_BACKOFF_S,
) -> _T:
    """Call ``fn()``, retrying up to ``max_retries`` times on a retryable failure only.

    Each retry logs a ``WARNING`` naming the venue and the attempt number, per the
    observability rule (a retry is a degraded-but-continuing condition). A non-retryable
    failure (4xx, or any exception :func:`is_retryable_http_error` rejects) propagates on
    the first attempt -- callers keep their existing failure handling unchanged.

    Parameters
    ----------
    fn
        Zero-argument callable performing the network call.
    venue
        Short identifier of the call site (provider/venue name), logged on retry.
    max_retries
        Retry attempts after the first try. Default :data:`MAX_RETRIES`.
    backoff_s
        Fixed delay between attempts. Default :data:`_RETRY_BACKOFF_S`.
    """
    attempt = 0
    while True:
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 -- filtered by is_retryable_http_error below
            if attempt >= max_retries or not is_retryable_http_error(exc):
                raise
            attempt += 1
            logger.warning(
                "%s: retryable error on attempt %d/%d, retrying: %s",
                venue,
                attempt,
                max_retries,
                sanitize_for_log(str(exc)),
            )
            time.sleep(backoff_s)
