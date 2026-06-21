"""Signal de retour à la moyenne du spread : z-score à bande d'hystérésis (promu de P02).

Promotion *PoC → fondation* de ``projects/02_spread_mean_reversion`` : la logique canonique
(z-score sur fenêtre glissante point-in-time + entrée/sortie à hystérésis) remonte ici comme
producteur réutilisable. Présuppose une relation cointégrée validée (skill ``/cointegration-analysis``).

Anti look-ahead : seules des données ``≤ t`` (via la ``GuardedView`` de P08) entrent dans le
signal à ``t``. Déterminisme : l'état d'hystérésis est réinitialisé à ``view.t == 0`` (deux
parcours sur la même série coïncident).
"""

from __future__ import annotations

from core.backtest.protocols import PointInTimeView
from core.signals.protocols import SignalProvenance

#: Nombre minimal d'observations pour définir un écart-type glissant.
_MIN_LOOKBACK: int = 2


class MeanReversionSignal:
    """Bande à hystérésis sur le z-score du spread (implémente ``SignalProducer``).

    Parameters
    ----------
    z_entry : float
        Seuil d'entrée : on prend position quand ``|z| >= z_entry``.
    z_exit : float
        Seuil de sortie : on revient à plat quand ``|z| <= z_exit``. Doit être ``< z_entry``
        (la bande morte ``[z_exit, z_entry]`` évite le papillonnage autour d'un seuil unique).
    lookback : int
        Fenêtre glissante d'estimation de la moyenne/écart-type du spread (``>= 2``).
    name : str
        Identifiant du signal (tracé MLflow / attribution desk).
    simulated : bool
        Drapeau réel/simulé **obligatoire** (rule ``forward-real-simulated``).

    Raises
    ------
    ValueError
        Si ``z_exit >= z_entry`` ou ``lookback < 2``.
    """

    def __init__(
        self,
        *,
        z_entry: float,
        z_exit: float,
        lookback: int,
        name: str = "mean_reversion",
        simulated: bool,
    ) -> None:
        if not z_exit < z_entry:
            raise ValueError(
                f"z_exit ({z_exit}) doit être < z_entry ({z_entry}) : bande morte vide."
            )
        if lookback < _MIN_LOOKBACK:
            raise ValueError(f"lookback ({lookback}) doit être >= {_MIN_LOOKBACK}.")
        self.z_entry = z_entry
        self.z_exit = z_exit
        self.lookback = lookback
        self.name = name
        self.provenance = SignalProvenance(name=name, simulated=simulated)
        self._position = 0.0

    def decide(self, *, z: float, current_position: float) -> float:
        """Transition de la bande à hystérésis : ``(z, position courante)`` → position cible.

        À plat, on entre **contre** la déviation (``z >= z_entry`` → short ``-1`` ; ``z <= -z_entry``
        → long ``+1``). En position, on **tient** tant que ``|z| > z_exit`` puis on **repasse à plat**
        (jamais de flip direct ``-1 ↔ +1`` : un z-score glissant traverse la zone de sortie avant
        d'atteindre la bande d'entrée opposée).
        """
        if current_position == 0.0:
            if z >= self.z_entry:
                return -1.0
            if z <= -self.z_entry:
                return 1.0
            return 0.0
        if abs(z) <= self.z_exit:
            return 0.0
        return current_position

    def signal(self, view: PointInTimeView) -> float:
        """Position cible à ``t`` : z-score du spread sur la fenêtre ``<= t`` → règle d'hystérésis.

        Réinitialise l'état à ``view.t == 0`` (reproductibilité). Historique insuffisant ou
        écart-type nul → on garde la position (rien de neuf à dire, point-in-time).
        """
        if view.t == 0:
            self._position = 0.0
        history = view.history()
        if history.size < self.lookback:
            return self._position
        recent = history[-self.lookback :]
        std = float(recent.std(ddof=1))
        if std == 0.0:
            return self._position
        z = (view.latest() - float(recent.mean())) / std
        self._position = self.decide(z=z, current_position=self._position)
        return self._position


__all__ = ["MeanReversionSignal"]
