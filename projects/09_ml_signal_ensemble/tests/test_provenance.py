"""Frontière réel/simulé : le flag ``simulated`` est obligatoire (rule forward-real-simulated).

Un dataset synthétique non étiqueté est un bug : le test échoue si l'on peut construire une
provenance sans se prononcer sur le caractère simulé, ou si le générateur n'étiquette pas.
"""

from __future__ import annotations

import pytest

from synthetic import DataProvenance, generate


def test_provenance_requires_simulated_flag() -> None:
    with pytest.raises(TypeError):
        DataProvenance(source="x")  # type: ignore[call-arg]  # simulated manquant → interdit


def test_generated_dataset_is_labelled_simulated() -> None:
    dataset = generate(n_days=120)
    assert dataset.provenance.simulated is True
    assert "synthetic" in dataset.provenance.source


def test_generation_is_deterministic() -> None:
    a = generate(n_days=150)
    b = generate(n_days=150)
    assert a.spread.equals(b.spread)
