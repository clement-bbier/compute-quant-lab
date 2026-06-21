"""Garde-fou anti look-ahead.

`GuardedView` enveloppe une série et n'expose que les valeurs ≤ t. Tout accès au
futur lève `LookAheadError` : c'est le mécanisme qui rend le biais de look-ahead
**impossible à ignorer** — un signal qui triche fait échouer le run.
"""

from __future__ import annotations

from core.backtest.protocols import FloatArray


class LookAheadError(RuntimeError):
    """Levée quand un signal tente de lire une donnée postérieure à l'instant t."""


class GuardedView:
    """Vue point-in-time sur une série : ne voit que ≤ t (implémente PointInTimeView)."""

    def __init__(self, data: FloatArray, t: int) -> None:
        if not 0 <= t < data.shape[0]:
            raise IndexError(f"t={t} hors bornes pour une série de longueur {data.shape[0]}")
        self._data = data
        self.t = t

    def history(self) -> FloatArray:
        """Copie des valeurs connues jusqu'à t inclus (pas d'aliasing avec les données du moteur)."""
        return self._data[: self.t + 1].copy()

    def latest(self) -> float:
        """Valeur à l'instant courant t."""
        return float(self._data[self.t])

    def at(self, i: int) -> float:
        """Valeur à l'index i. Lève `LookAheadError` si i > t, `IndexError` si i < 0.

        Les index négatifs sont refusés : `at(-1)` bouclerait en numpy vers la fin
        de la série (donc le futur), ce qui serait un look-ahead déguisé.
        """
        if i < 0:
            raise IndexError(f"index négatif refusé (wrap-around interdit) : i={i}")
        if i > self.t:
            raise LookAheadError(f"accès futur interdit : i={i} > t={self.t}")
        return float(self._data[i])
