"""Tests du signal directionnel dérivé de la pente (convention roll-yield).

Convention validée (commodités non stockables) : **backwardation → long (+1)**,
**contango → short (-1)**, pente dans la bande neutre → **0**.
"""

from __future__ import annotations

import datetime as dt

import pytest

from signals import directional_signal
from term_structure import TermStructure

_AS_OF = dt.datetime(2026, 6, 21, tzinfo=dt.timezone.utc)


def _ts(slope: float, shape: str) -> TermStructure:
    return TermStructure(
        front_price=2.0,
        slope=slope,
        curvature=0.0,
        shape=shape,  # type: ignore[arg-type]
        as_of=_AS_OF,
        simulated=True,
    )


def test_backwardation_gives_long_signal() -> None:
    assert directional_signal(_ts(-0.01, "backwardation")).value == +1


def test_contango_gives_short_signal() -> None:
    assert directional_signal(_ts(0.01, "contango")).value == -1


def test_flat_gives_neutral_signal() -> None:
    assert directional_signal(_ts(0.0, "flat")).value == 0


@pytest.mark.parametrize("shape", ["contango", "backwardation"])
def test_small_slope_inside_neutral_band_is_zero(shape: str) -> None:
    # |slope| sous la bande neutre -> pas de pari, même si la forme penche.
    sig = directional_signal(_ts(1e-9, shape), neutral_band=1e-6)
    assert sig.value == 0


def test_signal_value_is_in_minus_one_zero_plus_one() -> None:
    for shape, slope in (("contango", 0.01), ("backwardation", -0.01), ("flat", 0.0)):
        assert directional_signal(_ts(slope, shape)).value in (-1, 0, 1)
