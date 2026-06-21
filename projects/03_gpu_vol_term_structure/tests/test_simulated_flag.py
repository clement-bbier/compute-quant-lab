"""Garde-fou de la frontière réel/simulé (rule ``forward-real-simulated``).

Toute sortie dérivée de la forward DOIT porter un drapeau ``simulated`` explicite et
**non optionnel** : un test échoue si le champ est absent. Ce module verrouille
l'invariant au niveau du type (``TermStructure``) et de sa propagation (``DirectionalSignal``).
"""

from __future__ import annotations

import dataclasses
import datetime as dt

import pytest

from signals import DirectionalSignal, directional_signal
from term_structure import TermStructure


def test_term_structure_requires_simulated_flag() -> None:
    """Construire un TermStructure sans `simulated` doit échouer (champ obligatoire)."""
    fields = {f.name for f in dataclasses.fields(TermStructure)}
    assert "simulated" in fields
    simulated_field = next(f for f in dataclasses.fields(TermStructure) if f.name == "simulated")
    # Aucun défaut : impossible de l'omettre.
    assert simulated_field.default is dataclasses.MISSING
    assert simulated_field.default_factory is dataclasses.MISSING

    with pytest.raises(TypeError):
        TermStructure(  # type: ignore[call-arg]  # `simulated` volontairement omis
            front_price=2.0,
            slope=-0.01,
            curvature=0.0,
            shape="backwardation",
            as_of=dt.datetime(2026, 6, 21, tzinfo=dt.timezone.utc),
        )


def test_signal_propagates_simulated_flag() -> None:
    ts = TermStructure(
        front_price=2.0,
        slope=-0.01,
        curvature=0.0,
        shape="backwardation",
        as_of=dt.datetime(2026, 6, 21, tzinfo=dt.timezone.utc),
        simulated=True,
    )
    sig = directional_signal(ts)
    assert isinstance(sig, DirectionalSignal)
    assert sig.simulated is True
