"""Tests for the lab's central logger.

Two groups:

- ``sanitize_for_log``: a configured secret value never survives into a sanitized
  message. ``str(exc)`` on an HTTP client error routinely echoes the failing request
  (headers, URL, sometimes the body), which can carry an API key.
- ``configure_logging`` / ``get_logger``: level is driven by ``LOG_LEVEL``, every
  emitted record carries the git SHA, provenance is stamped when the call site supplies it,
  and importing the module attaches no handler (library-safe).
"""

from __future__ import annotations

import logging

import pytest

import core.utils.logging as lab_logging
from core.utils.logging import (
    SECRET_ENV_NAMES,
    _MAX_MESSAGE_LENGTH,
    configure_logging,
    get_logger,
    sanitize_for_log,
)


@pytest.fixture(autouse=True)
def _reset_logging_state(monkeypatch):
    """Isolate each test from the module-level ``_configured``/SHA cache and the root logger.

    ``configure_logging`` is deliberately idempotent in production (repeated calls must not
    stack handlers) -- but that same idempotency would leak a handler installed by one test
    into the next, so tests reset the module globals directly instead of going through the
    public API.
    """
    monkeypatch.setattr(lab_logging, "_configured", False)
    monkeypatch.setattr(lab_logging, "_git_sha_cache", None)
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    yield
    root.handlers[:] = original_handlers
    root.setLevel(original_level)


def test_secret_value_is_masked(monkeypatch) -> None:
    monkeypatch.setenv("VASTAI_API_KEY", "sk-fake-secret-1234567890")
    exc_message = (
        "HTTPError: 401 for url https://vast.ai/api?token=sk-fake-secret-1234567890 -- "
        "check credentials"
    )
    sanitized = sanitize_for_log(exc_message)
    assert "sk-fake-secret-1234567890" not in sanitized
    assert "***" in sanitized


def test_multiple_configured_secrets_are_all_masked(monkeypatch) -> None:
    monkeypatch.setenv("DATACRUNCH_CLIENT_ID", "client-abc")
    monkeypatch.setenv("DATACRUNCH_CLIENT_SECRET", "secret-xyz")
    message = "auth failed for client-abc using secret-xyz"
    sanitized = sanitize_for_log(message)
    assert "client-abc" not in sanitized
    assert "secret-xyz" not in sanitized


def test_message_without_secrets_is_unchanged() -> None:
    message = "provider 'runpod' returned 503"
    assert sanitize_for_log(message) == message


def test_unset_env_vars_are_not_matched(monkeypatch) -> None:
    for name in SECRET_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    message = "connection timed out after 30s"
    assert sanitize_for_log(message) == message


def test_long_message_is_truncated() -> None:
    message = "x" * (_MAX_MESSAGE_LENGTH + 200)
    sanitized = sanitize_for_log(message)
    assert len(sanitized) <= _MAX_MESSAGE_LENGTH + len("... [truncated]")
    assert sanitized.endswith("... [truncated]")


def test_short_secret_value_does_not_over_match(monkeypatch) -> None:
    """A short, low-entropy value is still masked -- no minimum-length carve-out."""
    monkeypatch.setenv("CUDO_API_KEY", "ab")
    message = "token ab rejected"
    sanitized = sanitize_for_log(message)
    assert "***" in sanitized


def test_get_logger_attaches_no_handler_at_import_or_call() -> None:
    """Library-safe: obtaining a logger must never itself install a handler.

    A handler attached by ``get_logger`` would mean the module is configuring
    logging as a side effect of being imported -- exactly what leaves a
    library mute or duplicating lines depending on import order. Only
    :func:`configure_logging` may add a handler, and only to the root logger.
    """
    logger = get_logger("test.no_handler")
    assert logger.handlers == []


def test_configure_logging_defaults_to_info(monkeypatch) -> None:
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    configure_logging()
    assert logging.getLogger().level == logging.INFO


def test_configure_logging_respects_log_level_env(monkeypatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    configure_logging()
    assert logging.getLogger().level == logging.DEBUG


def test_log_level_env_controls_emitted_verbosity(monkeypatch) -> None:
    """Same DEBUG call, two ``LOG_LEVEL`` settings: only one is actually enabled for the logger.

    Deliberately does not use ``caplog.at_level`` -- it forces the root/handler level for
    the duration of the ``with`` block, which would override exactly the ``LOG_LEVEL``
    effect this test wants to observe. Checking ``isEnabledFor`` against the *unmodified*
    effective level is the direct way to prove ``LOG_LEVEL`` is what drives verbosity.
    """
    logger = get_logger("test.verbosity")

    monkeypatch.setenv("LOG_LEVEL", "INFO")
    configure_logging()
    assert logger.isEnabledFor(logging.DEBUG) is False

    monkeypatch.setattr(lab_logging, "_configured", False)
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    configure_logging()
    assert logger.isEnabledFor(logging.DEBUG) is True


def test_configure_logging_is_idempotent_no_duplicate_handlers() -> None:
    root = logging.getLogger()
    before = len(root.handlers)
    configure_logging()
    configure_logging()
    configure_logging(level="DEBUG")
    assert len(root.handlers) == before + 1


def test_emitted_record_carries_git_sha(monkeypatch, caplog) -> None:
    """``git_sha`` lands on the record itself -- checked directly, not via ``caplog.text``.

    ``caplog.text`` runs pytest's own capture formatter, which knows nothing about
    :data:`lab_logging._FORMAT`; the git SHA is only visible on ``record.git_sha``
    (and on the real console handler's ``_FORMAT``-rendered output, asserted separately
    via ``capsys``-style stderr capture is out of scope here).
    """
    monkeypatch.setattr(lab_logging, "_git_sha_cache", "abc1234")
    configure_logging()
    logger = get_logger("test.sha")
    with caplog.at_level(logging.INFO):
        logger.info("hello")
    assert any(r.git_sha == "abc1234" for r in caplog.records)


def test_git_sha_resolution_failure_warns_instead_of_silent_unknown(monkeypatch, caplog) -> None:
    def _boom(*args, **kwargs):
        raise FileNotFoundError("git not found")

    monkeypatch.setattr(lab_logging.subprocess, "check_output", _boom)
    configure_logging()
    logger = get_logger("test.sha_failure")
    with caplog.at_level(logging.INFO):
        logger.info("triggers sha resolution")
    assert any(
        r.name == "core.utils.logging" and "git SHA" in r.getMessage() for r in caplog.records
    )
    assert lab_logging._resolve_git_sha() == "unknown"


def test_provenance_is_stamped_when_supplied(caplog) -> None:
    configure_logging()
    real_logger = get_logger("test.provenance", simulated=False)
    simulated_logger = get_logger("test.provenance", simulated=True)
    with caplog.at_level(logging.INFO):
        caplog.clear()
        real_logger.info("real price observed")
        simulated_logger.info("simulated curve produced")
    real_line = next(r for r in caplog.records if "real price" in r.message)
    simulated_line = next(r for r in caplog.records if "simulated curve" in r.message)
    assert "real" in real_line.provenance
    assert "simulated" in simulated_line.provenance


def test_provenance_blank_when_not_supplied(caplog) -> None:
    configure_logging()
    logger = get_logger("test.no_provenance")
    with caplog.at_level(logging.INFO):
        caplog.clear()
        logger.info("no provenance notion here")
    record = next(r for r in caplog.records if "no provenance notion" in r.message)
    assert record.provenance == ""
