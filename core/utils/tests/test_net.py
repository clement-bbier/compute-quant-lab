"""Tests for the shared HTTP retry/timeout policy (V7.2 observability -- budget-zero).

Two behaviours pinned:

- a retryable failure (5xx, timeout, connection error) is retried up to
  :data:`~core.utils.net.MAX_RETRIES` times, each attempt logged at WARNING;
- a non-retryable failure (4xx) propagates immediately, with **zero** retry -- retrying
  an unauthorized/malformed request would only burn a free-tier quota for nothing.
"""

from __future__ import annotations

import logging

import pytest
import requests

from core.utils.net import call_with_retry, is_retryable_http_error


def _http_error(status_code: int) -> requests.exceptions.HTTPError:
    response = requests.Response()
    response.status_code = status_code
    return requests.exceptions.HTTPError(response=response)


# -- is_retryable_http_error ----------------------------------------------------------


def test_5xx_is_retryable() -> None:
    assert is_retryable_http_error(_http_error(500)) is True
    assert is_retryable_http_error(_http_error(503)) is True


def test_4xx_is_not_retryable() -> None:
    assert is_retryable_http_error(_http_error(401)) is False
    assert is_retryable_http_error(_http_error(404)) is False


def test_timeout_is_retryable() -> None:
    assert is_retryable_http_error(requests.exceptions.Timeout("timed out")) is True


def test_connection_error_is_retryable() -> None:
    assert is_retryable_http_error(requests.exceptions.ConnectionError("refused")) is True


def test_unrelated_exception_is_not_retryable() -> None:
    assert is_retryable_http_error(ValueError("bad payload")) is False


# -- call_with_retry --------------------------------------------------------------------


def test_5xx_retries_then_succeeds(caplog: pytest.LogCaptureFixture) -> None:
    attempts = {"n": 0}

    def flaky() -> str:
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise _http_error(503)
        return "ok"

    with caplog.at_level(logging.WARNING):
        result = call_with_retry(flaky, venue="test-venue", backoff_s=0.0)

    assert result == "ok"
    assert attempts["n"] == 2
    assert "test-venue" in caplog.text
    assert "attempt 1/2" in caplog.text


def test_4xx_never_retries() -> None:
    attempts = {"n": 0}

    def unauthorized() -> str:
        attempts["n"] += 1
        raise _http_error(401)

    with pytest.raises(requests.exceptions.HTTPError):
        call_with_retry(unauthorized, venue="test-venue", backoff_s=0.0)

    assert attempts["n"] == 1  # zero retries: a 4xx would fail identically every time


def test_exhausts_retries_then_raises(caplog: pytest.LogCaptureFixture) -> None:
    attempts = {"n": 0}

    def always_503() -> str:
        attempts["n"] += 1
        raise _http_error(503)

    with caplog.at_level(logging.WARNING), pytest.raises(requests.exceptions.HTTPError):
        call_with_retry(always_503, venue="test-venue", max_retries=2, backoff_s=0.0)

    assert attempts["n"] == 3  # 1 initial try + 2 retries
    assert caplog.text.count("test-venue") >= 2


def test_non_retryable_exception_propagates_immediately() -> None:
    attempts = {"n": 0}

    def raises_value_error() -> str:
        attempts["n"] += 1
        raise ValueError("malformed schema")

    with pytest.raises(ValueError, match="malformed schema"):
        call_with_retry(raises_value_error, venue="test-venue", backoff_s=0.0)

    assert attempts["n"] == 1
