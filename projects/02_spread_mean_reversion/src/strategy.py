"""Stratégie de retour à la moyenne sur le spread (z-score à bande d'hystérésis).

Présuppose une relation cointégrée validée (``cointegration.py`` / skill ``/cointegration-analysis``).
On normalise le spread en z-score sur une fenêtre glissante **point-in-time**, puis on entre
contre la déviation quand ``|z|`` franchit ``z_entry`` et on revient à plat quand ``|z|`` retombe
sous ``z_exit`` (bande morte entre les deux = anti-papillonnage). Implémente le ``Strategy``
Protocol de ``core.backtest`` (P08) : seules des données ≤ t entrent dans le signal à t.
"""

from __future__ import annotations

from core.backtest import PointInTimeView


class MeanReversionStrategy:
    """Bande à hystérésis sur le z-score du spread (implémente le ``Strategy`` Protocol de P08).

    Parameters
    ----------
    z_entry : float
        Seuil d'entrée : on prend position quand ``|z| >= z_entry``.
    z_exit : float
        Seuil de sortie : on revient à plat quand ``|z| <= z_exit``. Doit être ``< z_entry``
        (la bande morte ``[z_exit, z_entry]`` évite le papillonnage autour d'un seuil unique).
    lookback : int
        Taille de la fenêtre glissante d'estimation de la moyenne/écart-type du spread (≥ 2).

    Raises
    ------
    ValueError
        Si ``z_exit >= z_entry`` ou ``lookback < 2``.
    """

    def __init__(self, *, z_entry: float, z_exit: float, lookback: int) -> None:
        if not z_exit < z_entry:
            raise ValueError(
                f"z_exit ({z_exit}) doit être < z_entry ({z_entry}) : bande morte vide."
            )
        if lookback < 2:
            raise ValueError(f"lookback ({lookback}) doit être ≥ 2 (écart-type non défini sinon).")
        self.z_entry = z_entry
        self.z_exit = z_exit
        self.lookback = lookback
        self._position = 0.0

    def decide(self, *, z: float, current_position: float) -> float:
        """Règle de transition de la bande à hystérésis : (z, position courante) → position cible.

        Choix de design par défaut (modifiable) :
        - à plat, on entre **contre** la déviation : ``z >= z_entry`` → short (-1), ``z <= -z_entry`` → long (+1) ;
        - en position, on **tient** tant que ``|z| > z_exit``, puis on **repasse à plat** (jamais de
          flip direct -1↔+1 : un z-score glissant traverse forcément la zone de sortie avant de
          rejoindre la bande d'entrée opposée).
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
        """Position cible à t : z-score du spread sur la fenêtre ``≤ t`` → règle d'hystérésis.

        L'état est réinitialisé quand ``view.t == 0`` pour que deux runs sur la même série soient
        identiques (déterminisme). Historique insuffisant ou écart-type nul → on garde la position.
        """
        if view.t == 0:
            self._position = 0.0  # début d'un run : repart à plat (reproductibilité)
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
