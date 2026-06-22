"""Configuration pytest pour les tests core/ingestion/energy/.

Registre du marker ``live`` : les tests réels ERCOT (réseau) sont exclus
par défaut et lancés explicitement via ``pytest -m live``.
"""

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "live: smoke test réel (réseau ERCOT requis) — exclu par défaut",
    )
