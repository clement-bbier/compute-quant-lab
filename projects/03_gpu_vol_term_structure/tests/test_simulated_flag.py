"""Guardrail for the real/simulated boundary (rule ``forward-real-simulated``).

Any output derived from the forward MUST carry an explicit and **non-optional**
``simulated`` flag: a test fails if the field is absent. This module locks
the invariant at the type level (``TermStructure``) and its propagation (``DirectionalSignal``).
"""

from __future__ import annotations

import dataclasses
import datetime as dt

import pytest

from signals import DirectionalSignal, directional_signal
from term_structure import TermStructure


def test_term_structure_requires_simulated_flag() -> None:
    """Constructing a TermStructure without `simulated` must fail (required field)."""
    fields = {f.name for f in dataclasses.fields(TermStructure)}
    assert "simulated" in fields
    simulated_field = next(f for f in dataclasses.fields(TermStructure) if f.name == "simulated")
    # No default: impossible to omit it.
    assert simulated_field.default is dataclasses.MISSING
    assert simulated_field.default_factory is dataclasses.MISSING

    with pytest.raises(TypeError):
        TermStructure(  # type: ignore[call-arg]  # `simulated` deliberately omitted
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
