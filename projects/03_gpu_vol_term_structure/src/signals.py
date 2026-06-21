"""Signal directionnel dérivé de la structure par terme (pur).

Convention **roll-yield** des commodités non stockables (analogie électricité), validée
avec le directeur de recherche :

- **backwardation** (courbe décroissante, forward < spot) → carry positif côté long → **+1** ;
- **contango** (courbe croissante, forward > spot) → carry négatif → **-1** ;
- pente dans la **bande neutre** (forme plate ou |pente| < seuil) → **0** (pas de pari).

⚠️ La forward compute étant SIMULÉE, le signal hérite du drapeau ``simulated`` du
:class:`~term_structure.TermStructure` source : aucun signal n'est présenté comme dérivé
d'un prix réel (rule ``forward-real-simulated``).
"""

from __future__ import annotations

from dataclasses import dataclass

from term_structure import TermStructure

#: Bande neutre par défaut sur |pente| ($/GPU·h par jour) en deçà de laquelle on ne parie pas.
DEFAULT_NEUTRAL_BAND = 1e-5


@dataclass(frozen=True)
class DirectionalSignal:
    """Signal directionnel discret. ``simulated`` propagé depuis la term structure."""

    value: int  # -1 (short) | 0 (neutre) | +1 (long)
    rationale: str
    simulated: bool


def directional_signal(
    term: TermStructure,
    *,
    neutral_band: float = DEFAULT_NEUTRAL_BAND,
) -> DirectionalSignal:
    """Traduit la forme/pente de la courbe en signal -1/0/+1 (convention roll-yield).

    Parameters
    ----------
    term
        Résultat d'analyse de la term structure (porte la pente, la forme, ``simulated``).
    neutral_band
        Seuil sur ``|term.slope|`` sous lequel on reste neutre (pas de pari).

    Returns
    -------
    DirectionalSignal
        ``+1`` si backwardation franche, ``-1`` si contango franc, ``0`` sinon.
    """
    if abs(term.slope) < neutral_band or term.shape == "flat":
        return DirectionalSignal(0, "pente dans la bande neutre (pas de pari)", term.simulated)
    if term.shape == "backwardation":
        return DirectionalSignal(
            +1, "backwardation : carry positif côté long (roll-yield)", term.simulated
        )
    return DirectionalSignal(-1, "contango : carry négatif (roll-yield)", term.simulated)
