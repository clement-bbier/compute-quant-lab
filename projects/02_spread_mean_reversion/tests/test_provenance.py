"""Garde-fou réel/simulé (rule ``forward-real-simulated``).

Toute série servie à la stratégie doit déclarer explicitement son origine : un test **échoue**
si le drapeau ``simulated`` est absent. On n'expose jamais une série simulée comme réelle.
"""

from __future__ import annotations

import pytest

from data_sources import DataProvenance


def test_provenance_requires_explicit_simulated_flag() -> None:
    with pytest.raises(TypeError):
        DataProvenance(source="vastai")  # type: ignore[call-arg]  # 'simulated' manquant → refus


def test_provenance_distinguishes_real_from_simulated() -> None:
    assert DataProvenance(source="entsoe+vastai", simulated=False).simulated is False
    assert DataProvenance(source="synthetic_ou", simulated=True).simulated is True
