"""Real/simulated boundary: the ``simulated`` flag is MANDATORY (rule forward-real-simulated).

At the PoC stage, all signal producers are mocked → simulated. A test MUST fail if the
flag is missing, so that no mock PnL is ever mistaken for real alpha.
"""

from __future__ import annotations

import pytest

from provenance import SignalProvenance


def test_simulated_flag_is_mandatory() -> None:
    """Constructing a provenance without specifying ``simulated`` raises a TypeError."""
    with pytest.raises(TypeError):
        SignalProvenance(name="mock")  # type: ignore[call-arg]  # missing flag → forbidden


def test_provenance_carries_name_and_flag() -> None:
    """The name and simulated flag are preserved as-is."""
    prov = SignalProvenance(name="mean_reversion_mock", simulated=True)
    assert prov.name == "mean_reversion_mock"
    assert prov.simulated is True


def test_provenance_is_immutable() -> None:
    """Provenance is frozen: a simulated signal cannot be relabeled as real afterwards."""
    prov = SignalProvenance(name="mock", simulated=True)
    with pytest.raises(Exception):
        prov.simulated = False  # type: ignore[misc]  # frozen dataclass
