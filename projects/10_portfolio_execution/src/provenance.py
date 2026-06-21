"""Provenance d'un signal : réel vs simulé (frontière non négociable).

Au PoC, les producteurs de signaux du desk sont mockés (placeholders P02/P06/P09) → tous
``simulated=True``. Le flag est **sans défaut** : impossible d'oublier d'étiqueter un signal
(rule ``forward-real-simulated``). On ne vend jamais un PnL mock comme de l'alpha.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SignalProvenance:
    """Origine d'un signal. ``simulated`` est obligatoire (aucune valeur par défaut)."""

    name: str
    simulated: bool
