"""Provider fetches retry on 5xx, never on 4xx (budget-zero).

Uses ``vastai`` as the representative venue (single GET call, simplest shape); the retry
policy itself lives in ``core.utils.net`` and is unit-tested there directly. This file
pins the *integration*: a provider's ``fetch_<venue>`` call actually goes through
``call_with_retry`` with the shared timeout, end to end.
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any

import pytest
import requests

from core.ingestion.providers import vastai
from core.utils import net as net_module

_TS = dt.datetime(2026, 6, 21, tzinfo=dt.timezone.utc)


class _FakeResponse:
    def __init__(self, payload: Any, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            response = requests.Response()
            response.status_code = self.status_code
            raise requests.exceptions.HTTPError(response=response)

    def json(self) -> Any:
        return self._payload


def test_5xx_then_success_retries_and_returns_offers(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    calls = {"n": 0}
    offers = [{"gpu_name": "H100 SXM", "dph_total": 16.0, "num_gpus": 8, "rentable": True}]

    def _flaky_get(*a: Any, **k: Any) -> _FakeResponse:
        calls["n"] += 1
        if calls["n"] < 2:
            return _FakeResponse(None, status_code=503)
        return _FakeResponse({"offers": offers})

    monkeypatch.setattr(vastai.requests, "get", _flaky_get)
    monkeypatch.setattr(net_module.time, "sleep", lambda _s: None)

    with caplog.at_level(logging.WARNING):
        snaps = vastai.fetch_vastai("dummy-key", _TS)

    assert calls["n"] == 2
    assert len(snaps) == 1
    assert snaps[0].source == "vastai"
    assert "vastai" in caplog.text
    assert "retrying" in caplog.text.lower()


def test_4xx_raises_immediately_with_zero_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def _unauthorized_get(*a: Any, **k: Any) -> _FakeResponse:
        calls["n"] += 1
        return _FakeResponse(None, status_code=401)

    monkeypatch.setattr(vastai.requests, "get", _unauthorized_get)

    with pytest.raises(requests.exceptions.HTTPError):
        vastai.fetch_vastai("dummy-key", _TS)

    assert calls["n"] == 1  # a 4xx must never be retried (quota is precious)
