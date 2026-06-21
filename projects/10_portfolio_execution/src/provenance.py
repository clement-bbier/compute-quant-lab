"""Provenance d'un signal : réel vs simulé (frontière non négociable).

P12 a **promu** la provenance canonique dans ``core.signals`` (fondation réutilisable). Ce module
la **ré-exporte** pour rester rétro-compatible (``from provenance import SignalProvenance``) : un
seul type partagé entre les mocks du PoC et les vrais producteurs (P02/P06/P09), sans duplication.

Le flag ``simulated`` reste **sans défaut** : impossible d'oublier d'étiqueter un signal (rule
``forward-real-simulated``). On ne vend jamais un PnL mock comme de l'alpha.
"""

from __future__ import annotations

from core.signals import SignalProvenance

__all__ = ["SignalProvenance"]
