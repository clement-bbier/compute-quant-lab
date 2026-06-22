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


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Exclut automatiquement les tests @live sauf si ``-m live`` est passé explicitement."""
    if config.option.markexpr == "live":
        # L'utilisateur a demandé explicitement les tests live → on ne filtre pas
        return
    skip_live = pytest.mark.skip(reason="test live : passe -m live pour l'exécuter")
    for item in items:
        if item.get_closest_marker("live"):
            item.add_marker(skip_live)
