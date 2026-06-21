"""Producteurs de signaux génériques + mocks déterministes (placeholders P02/P06/P09).

Un ``SignalProducer`` rend, à chaque instant t, une **vue directionnelle** ``s ∈ [-1, 1]``
à partir de données ≤ t (il consomme la ``PointInTimeView`` du moteur P08). C'est le contrat
que respecteront les vrais signaux à la convergence — mean-reversion (P02), dérivés (P06),
ML (P09) — sans que le desk change de code (OCP).

Au PoC, on fournit trois mocks **sans état** (donc trivialement déterministes), tous étiquetés
simulés : ``ConstantMock`` (carry/biais directionnel constant), ``MeanReversionMock`` (fade la
déviation, style P02), ``MomentumMock`` (suit la tendance, style P06/P09). Leur pertinence
économique est hors sujet : ce sont des bouchons.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from core.backtest import PointInTimeView

from provenance import SignalProvenance


@runtime_checkable
class SignalProducer(Protocol):
    """Source d'un signal directionnel point-in-time, étiquetée par sa provenance.

    Compatible avec le ``Strategy`` Protocol de P08 (``signal(view) -> float``), mais la
    sortie est interprétée comme une **vue normalisée** dans [-1, 1], pas une position finale :
    c'est le ``PortfolioConstructor`` qui décide de la taille.
    """

    name: str
    provenance: SignalProvenance

    def signal(self, view: PointInTimeView) -> float: ...


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
