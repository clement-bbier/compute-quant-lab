"""pytest configuration for the core/ingestion/energy/ tests.

Registers the ``live`` marker: the real ERCOT tests (network) are excluded by default and run
explicitly via ``pytest -m live``.
"""

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "live: real smoke test (ERCOT network required) -- excluded by default",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Automatically exclude the @live tests unless ``-m live`` is passed explicitly."""
    if config.option.markexpr == "live":
        # The user explicitly asked for the live tests -> do not filter
        return
    skip_live = pytest.mark.skip(reason="live test: pass -m live to run it")
    for item in items:
        if item.get_closest_marker("live"):
            item.add_marker(skip_live)
