"""Socle du sous-paquet ``energy`` : protocole de marché + registre key-gated.

Définit l'abstraction d'injection :class:`EnergyMarket` (un connecteur = un marché
énergétique) et le registre key-gated, **calqué sur** ``core.ingestion.providers.base``
(pattern W1/W2 du labo). Principe OCP : *ajouter un marché = ajouter un fichier*,
sans toucher au cœur.

Point-in-time L0
----------------
La prévision de réserve (:meth:`EnergyMarket.reserve_forecast`) doit être horodatée
à son **heure de publication** (colonne ``publish_time``), jamais à l'heure cible.
Cela garantit que la couche calibration (P07) ne consomme que de la donnée connue
à l'instant de décision (~18h00 CPT J-1 pour ERCOT), sans look-ahead.

Registre key-gated
------------------
Un marché dont ``required_env`` est non vide n'est listé dans
:func:`available_markets` que si **toutes** ses clés sont présentes dans
l'environnement. ERCOT est public (``required_env = ()``), donc toujours listé.
"""

from __future__ import annotations

import os
from typing import Protocol, runtime_checkable

import pandas as pd

# ---------------------------------------------------------------------------
# Protocole injectable
# ---------------------------------------------------------------------------


@runtime_checkable
class EnergyMarket(Protocol):
    """Source de prix d'un marché énergétique (injectable, key-gated).

    Un connecteur = un marché. Le registre (:mod:`core.ingestion.energy`) n'expose
    un marché dans :func:`available_markets` que si **toutes** les ``required_env``
    sont présentes ; sinon il est silencieusement masqué.

    Contrat point-in-time (L0 §2)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    :meth:`reserve_forecast` doit inclure une colonne ``publish_time`` (UTC tz-aware)
    horodatée à l'heure de **publication** du rapport ERCOT, pas à l'heure cible.
    La calibration L0 utilise ``publish_time`` pour filtrer causalement (cutoff 18h CPT J-1).
    """

    #: Identifiant court du marché (ex. ``"ercot"``).
    name: str
    #: Clés d'environnement nécessaires (gate du registre). Vide = public.
    required_env: tuple[str, ...]

    def rtm_price(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series:
        """Prix de règlement temps-réel (RTM) sur [start, end].

        Parameters
        ----------
        start, end
            Bornes de la plage temporelle (UTC tz-aware recommandé ; le connecteur
            fait la conversion depuis le fuseau local du marché).

        Returns
        -------
        pd.Series
            Série indexée par ``Interval Start`` (UTC tz-aware), valeurs en $/MWh,
            triée chronologiquement, sans NaN injectés. Nom de la série :
            ``"rtm_price_usd_mwh"``.
        """
        ...

    def reserve_forecast(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        """Prévision de marge de réserve publiée dans la plage [start, end].

        Point-in-time : retourne **tous les rapports publiés** entre ``start`` et
        ``end`` (publication range, pas cible range). L'appelant filtre ensuite
        sur ``publish_time <= cutoff``.

        Returns
        -------
        pd.DataFrame
            Colonnes minimales :

            - ``publish_time``       : pd.Timestamp UTC — heure de publication du rapport.
            - ``interval_start``     : pd.Timestamp UTC — heure cible de l'intervalle.
            - ``interval_end``       : pd.Timestamp UTC — fin de l'intervalle cible.
            - ``forecast_load_mw``   : float — charge prévue (MW).
            - ``forecast_capacity_mw`` : float — capacité disponible prévue (MW).
            - ``reserve_margin_mw``  : float — marge = capacité − charge (MW).

            Triée par (``publish_time``, ``interval_start``).
        """
        ...


# ---------------------------------------------------------------------------
# Registre key-gated
# ---------------------------------------------------------------------------

#: Registre interne : key → instance EnergyMarket.
_REGISTRY: dict[str, EnergyMarket] = {}


def register_market(key: str):
    """Décorateur d'enregistrement d'un marché dans le registre global.

    Usage
    -----
    ::

        @register_market("ercot")
        class ErcotMarket:
            name = "ercot"
            required_env = ()
            ...

    Le marché enregistré est accessible via :func:`get_market` et listé dans
    :func:`available_markets` si ses clés d'environnement sont présentes.
    """

    def _decorator(cls: type) -> type:
        _REGISTRY[key] = cls()
        return cls

    return _decorator


def get_market(key: str) -> EnergyMarket:
    """Récupère une instance de marché par sa clé.

    Raises
    ------
    KeyError
        Si le marché n'est pas enregistré.
    """
    if key not in _REGISTRY:
        raise KeyError(f"Marché '{key}' non enregistré. Marchés connus : {list(_REGISTRY)}")
    return _REGISTRY[key]


def available_markets() -> list[str]:
    """Liste les marchés dont toutes les clés d'environnement sont présentes.

    Un marché avec ``required_env = ()`` est toujours listé (public).
    Un marché key-gated est masqué si l'une de ses clés est absente du shell.
    """
    result = []
    for key, market in _REGISTRY.items():
        if all(os.environ.get(env) for env in market.required_env):
            result.append(key)
    return result
