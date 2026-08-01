"""Directional signal derived from the term structure (pure).

**Roll-yield** convention for non-storable commodities (electricity analogy), validated
with the research director:

- **backwardation** (downward-sloping curve, forward < spot) → positive carry on the long side → **+1**;
- **contango** (upward-sloping curve, forward > spot) → negative carry → **-1**;
- slope within the **neutral band** (flat shape or |slope| < threshold) → **0** (no bet).

Warning: since the compute forward is SIMULATED, the signal inherits the ``simulated`` flag from the
source :class:`~term_structure.TermStructure`: no signal is presented as derived from
a real price (rule ``forward-real-simulated``).
"""

from __future__ import annotations

from dataclasses import dataclass

from term_structure import TermStructure

#: Default neutral band on |slope| ($/GPU·h per day) below which no bet is placed.
DEFAULT_NEUTRAL_BAND = 1e-5


@dataclass(frozen=True)
class DirectionalSignal:
    """Discrete directional signal. ``simulated`` propagated from the term structure."""

    value: int  # -1 (short) | 0 (neutral) | +1 (long)
    rationale: str
    simulated: bool


def directional_signal(
    term: TermStructure,
    *,
    neutral_band: float = DEFAULT_NEUTRAL_BAND,
) -> DirectionalSignal:
    """Translates the curve's shape/slope into a -1/0/+1 signal (roll-yield convention).

    Parameters
    ----------
    term
        Term structure analysis result (carries slope, shape, ``simulated``).
    neutral_band
        Threshold on ``|term.slope|`` below which we stay neutral (no bet).

    Returns
    -------
    DirectionalSignal
        ``+1`` for clear backwardation, ``-1`` for clear contango, ``0`` otherwise.
    """
    if abs(term.slope) < neutral_band or term.shape == "flat":
        return DirectionalSignal(0, "slope within the neutral band (no bet)", term.simulated)
    if term.shape == "backwardation":
        return DirectionalSignal(
            +1, "backwardation: positive carry on the long side (roll-yield)", term.simulated
        )
    return DirectionalSignal(-1, "contango: negative carry (roll-yield)", term.simulated)
