"""Tests for the secret-masking log sanitizer (V5.2 live-validation campaign).

``sanitize_for_log`` exists because ``str(exc)`` on an HTTP client error routinely echoes
the failing request (headers, URL, sometimes the body), which can carry an API key. These
tests prove a configured secret value never survives into a sanitized message.
"""

from __future__ import annotations

from core.utils.logging import (
    SECRET_ENV_NAMES,
    _MAX_MESSAGE_LENGTH,
    sanitize_for_log,
)


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
