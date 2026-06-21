"""Analyse de la structure par terme de la courbe forward compute (pure).

La forme de la courbe forward (contango/backwardation) porte de l'information
directionnelle. Ce module en extrait, **sans I/O**, trois descripteurs point-in-time :

- **pente** : régression linéaire prix ~ échéance (``np.polyfit`` degré 1) ;
- **courbure** : butterfly ``F_court − 2·F_milieu + F_long`` (convexité de la courbe) ;
- **forme** : contango / backwardation / plat selon un seuil ``flat_tol`` nommé.

⚠️ Frontière réel/simulé (rule ``forward-real-simulated``) : le résultat
:class:`TermStructure` porte un champ ``simulated`` **obligatoire** (sans défaut). La
forward compute étant simulée (futures CME non listés), un résultat sans étiquetage
explicite est interdit — la garantie est portée par le type.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Literal

import numpy as np

Shape = Literal["contango", "backwardation", "flat"]

#: Seuil par défaut de platitude de la pente ($/GPU·h par jour) sous lequel on classe 'flat'.
DEFAULT_FLAT_TOL = 1e-5


@dataclass(frozen=True)
class TermStructure:
    """Descripteurs de la courbe forward à un instant. ``simulated`` est OBLIGATOIRE.

    ``slope`` en $/GPU·h par jour, ``curvature`` en $/GPU·h (butterfly). ``shape``
    résume la forme. ``as_of`` horodate le fix (point-in-time).
    """

    front_price: float
    slope: float
    curvature: float
    shape: Shape
    as_of: dt.datetime
    simulated: bool


@dataclass(frozen=True)
class TermStructureAnalyzer:
    """Analyseur pur de courbe forward (Strategy, paramètre de seuil injectable)."""

    flat_tol: float = DEFAULT_FLAT_TOL

    def analyze(
        self,
        maturities: np.ndarray,
        prices: np.ndarray,
        *,
        simulated: bool,
        as_of: dt.datetime,
    ) -> TermStructure:
        """Calcule pente, courbure et forme de la courbe ``(maturities, prices)``.

        Parameters
        ----------
        maturities
            Échéances (jours), croissantes, longueur >= 3.
        prices
            Prix forward alignés sur ``maturities`` ($/GPU·h).
        simulated
            Drapeau réel/simulé propagé dans le résultat (obligatoire).
        as_of
            Instant du fix (UTC), horodaté dans le résultat.

        Returns
        -------
        TermStructure
            Descripteurs + drapeau ``simulated``.
        """
        m = np.asarray(maturities, dtype=float)
        p = np.asarray(prices, dtype=float)
        if m.ndim != 1 or m.size < 3 or m.shape != p.shape:
            raise ValueError("maturities/prices doivent être 1D alignés, longueur >= 3.")

        slope = float(np.polyfit(m, p, 1)[0])
        # Butterfly sur (premier, médian, dernier) point de la courbe : convexité.
        mid = p.size // 2
        curvature = float(p[0] - 2.0 * p[mid] + p[-1])

        if slope > self.flat_tol:
            shape: Shape = "contango"
        elif slope < -self.flat_tol:
            shape = "backwardation"
        else:
            shape = "flat"

        return TermStructure(
            front_price=float(p[0]),
            slope=slope,
            curvature=curvature,
            shape=shape,
            as_of=as_of,
            simulated=simulated,
        )
