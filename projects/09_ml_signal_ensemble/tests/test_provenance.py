"""Real/simulated boundary: the ``simulated`` flag is mandatory (forward-real-simulated rule).

An unlabeled synthetic dataset is a bug: the test fails if a provenance can be built
without stating whether it's simulated, or if the generator fails to label it.
"""

from __future__ import annotations

import pytest

from synthetic import DataProvenance, generate


def test_provenance_requires_simulated_flag() -> None:
    with pytest.raises(TypeError):
        DataProvenance(source="x")  # type: ignore[call-arg]  # missing simulated -> forbidden


def test_generated_dataset_is_labelled_simulated() -> None:
    dataset = generate(n_days=120)
    assert dataset.provenance.simulated is True
    assert "synthetic" in dataset.provenance.source


def test_generation_is_deterministic() -> None:
    a = generate(n_days=150)
    b = generate(n_days=150)
    assert a.spread.equals(b.spread)
