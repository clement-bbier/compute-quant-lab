"""Mocks de signaux déterministes (placeholders du PoC) + ré-export du contrat canonique.

Le contrat ``SignalProducer`` et la provenance vivent désormais dans ``core.signals`` (fondation
promue par P12) ; on les **ré-exporte** ici pour la rétro-compatibilité. Les **vrais** producteurs
(mean-reversion P02, basis futures P06, ML P09) sont dans ``core.signals`` et se branchent dans le
desk via ``run_desk.REAL_PRODUCERS`` sans que le desk change de code (OCP).

Les mocks ci-dessous restent pour les tests de régression du desk (cas analytiques, anti
look-ahead, DI) : trois bouchons **sans état**, étiquetés simulés — ``ConstantMock`` (carry
constant), ``MeanReversionMock`` (fade la déviation, style P02), ``MomentumMock`` (suit la
tendance, style P06/P09). Leur pertinence économique est hors sujet.
"""

from __future__ import annotations

from core.backtest import PointInTimeView
from core.signals import SignalProducer

from provenance import SignalProvenance

__all__ = [
    "SignalProducer",
    "ConstantMock",
    "MeanReversionMock",
    "MomentumMock",
]


def _clip_unit(value: float) -> float:
    """Écrête une vue directionnelle à l'intervalle [-1, 1]."""
    return max(-1.0, min(1.0, value))


def _zscore(view: PointInTimeView, lookback: int) -> float | None:
    """Z-score de la valeur courante sur la fenêtre ``≤ t`` de taille ``lookback``.

    Renvoie ``None`` si l'historique est trop court (< ``lookback``) ou si l'écart-type est
    nul (fenêtre plate) : dans ces cas, aucun signal n'est défini → l'appelant reste neutre.
    """
    history = view.history()
    if history.size < lookback:
        return None
    recent = history[-lookback:]
    std = float(recent.std(ddof=1))
    if std == 0.0:
        return None
    return (view.latest() - float(recent.mean())) / std


class ConstantMock:
    """Signal directionnel constant (placeholder d'un biais de carry). ``value`` écrêté à [-1, 1]."""

    def __init__(self, value: float, *, name: str = "constant_mock") -> None:
        self._value = _clip_unit(value)
        self.name = name
        self.provenance = SignalProvenance(name=name, simulated=True)

    def signal(self, view: PointInTimeView) -> float:
        """Renvoie la valeur constante, indépendamment de l'instant (mais via la vue garde-fou)."""
        return self._value


class MeanReversionMock:
    """Fade la déviation : ``s = clip(-z, -1, 1)`` (placeholder P02). Sans état → déterministe."""

    def __init__(self, lookback: int, *, name: str = "mean_reversion_mock") -> None:
        if lookback < 2:
            raise ValueError(f"lookback ({lookback}) doit être ≥ 2 (écart-type non défini sinon).")
        self.lookback = lookback
        self.name = name
        self.provenance = SignalProvenance(name=name, simulated=True)

    def signal(self, view: PointInTimeView) -> float:
        """Position cible directionnelle à t : on vend au-dessus de la moyenne, on achète en dessous."""
        z = _zscore(view, self.lookback)
        return 0.0 if z is None else _clip_unit(-z)


class MomentumMock:
    """Suit la tendance : ``s = clip(z, -1, 1)`` (placeholder P06/P09). Opposé du mean-reversion."""

    def __init__(self, lookback: int, *, name: str = "momentum_mock") -> None:
        if lookback < 2:
            raise ValueError(f"lookback ({lookback}) doit être ≥ 2 (écart-type non défini sinon).")
        self.lookback = lookback
        self.name = name
        self.provenance = SignalProvenance(name=name, simulated=True)

    def signal(self, view: PointInTimeView) -> float:
        """Position cible directionnelle à t : on achète quand le prix est au-dessus de sa moyenne."""
        z = _zscore(view, self.lookback)
        return 0.0 if z is None else _clip_unit(z)
