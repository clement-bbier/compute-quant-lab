"""Frontière réel/simulé : le flag ``simulated`` est OBLIGATOIRE (rule forward-real-simulated).

Au PoC, tous les producteurs de signaux sont mockés → simulés. Un test DOIT échouer si le
flag manque, pour qu'aucun PnL mock ne soit jamais confondu avec de l'alpha réel.
"""

from __future__ import annotations

import pytest

from provenance import SignalProvenance


def test_simulated_flag_is_mandatory() -> None:
    """Construire une provenance sans préciser ``simulated`` lève une TypeError."""
    with pytest.raises(TypeError):
        SignalProvenance(name="mock")  # type: ignore[call-arg]  # flag manquant → interdit


def test_provenance_carries_name_and_flag() -> None:
    """Le nom et le flag simulé sont conservés tels quels."""
    prov = SignalProvenance(name="mean_reversion_mock", simulated=True)
    assert prov.name == "mean_reversion_mock"
    assert prov.simulated is True


def test_provenance_is_immutable() -> None:
    """La provenance est gelée : on ne réétiquette pas un signal simulé en réel après coup."""
    prov = SignalProvenance(name="mock", simulated=True)
    with pytest.raises(Exception):
        prov.simulated = False  # type: ignore[misc]  # frozen dataclass
