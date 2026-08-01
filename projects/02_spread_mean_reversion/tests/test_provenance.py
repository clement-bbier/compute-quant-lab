"""Real/simulated guard (rule ``forward-real-simulated``).

Every series served to the strategy must explicitly declare its origin: a test **fails**
if the ``simulated`` flag is missing. A simulated series is never exposed as real.
"""

from __future__ import annotations

import pytest

from data_sources import DataProvenance


def test_provenance_requires_explicit_simulated_flag() -> None:
    with pytest.raises(TypeError):
        DataProvenance(source="vastai")  # type: ignore[call-arg]  # 'simulated' missing -> rejected


def test_provenance_distinguishes_real_from_simulated() -> None:
    assert DataProvenance(source="entsoe+vastai", simulated=False).simulated is False
    assert DataProvenance(source="synthetic_ou", simulated=True).simulated is True
