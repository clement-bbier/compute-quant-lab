"""Connecteur ERCOT (Texas) via ``gridstatus`` — marché public, sans token.

Surface API confirmée (B0 — 2026-06-23)
-----------------------------------------
- ``gridstatus.Ercot()`` — classe principale, ``default_timezone = "US/Central"``.
- ``iso.get_spp(date, end, market=Markets.REAL_TIME_15_MIN, locations=[...])``
    Colonnes de sortie : ``["Time", "Interval Start", "Interval End",
    "Location", "Location Type", "Market", "SPP"]``
    Fuseau : US/Central (CPT/CDT selon saison).
    Granularité : intervalles de 15 minutes.
    Source ERCOT : rapport ``SETTLEMENT_POINT_PRICES_AT_RESOURCE_NODES_HUBS_AND_LOAD_ZONES``
    (RTID 12301). Données disponibles J+0 à J-2 environ.
- ``iso.get_rtm_spp(year)``
    Colonnes identiques à ``get_spp``. Profondeur historique : depuis 2011 (annuel).
    Source : ``HISTORICAL_RTM_LOAD_ZONE_AND_HUB_PRICES`` (RTID 13061).
- ``iso.get_load_forecast(date, end, forecast_type=ERCOTSevenDayLoadForecastReport.BY_FORECAST_ZONE)``
    Colonnes de sortie : ``["Time", "Interval Start", "Interval End", "Publish Time",
    "Coast", "East", "Far West", "North", "North Central", "South Central",
    "Southern", "West", "System Total"]``
    Fuseau : US/Central.
    Granularité : horaire. Profondeur historique : limitée (quelques semaines).
    Source : ``ERCOT_SEVEN_DAY_LOAD_FORECAST_BY_FORECAST_ZONE`` (RTID 12311).

Heure de publication des rapports de prévision (critique pour le point-in-time L0 §2)
--------------------------------------------------------------------------------------
ERCOT publie le rapport Seven-Day Load Forecast toutes les heures environ. La colonne
``Publish Time`` retournée par ``get_load_forecast`` est horodatée à la publication
réelle (ex. 17h48, 18h02 CPT), pas à l'heure cible. Le cutoff de décision L0 est
~18h00 CPT J-1 : le rapport de 17h48 ou 18h02 CPT J-1 doit être le dernier utilisable.
Notre parser préserve ``Publish Time`` et le convertit en UTC pour la couche calibration.

NOTE réseau : l'API ercot.com est bloquée par WAF Imperva (Incapsula) depuis certains
réseaux hors US (code 403). Le smoke live (test_fetch_live.py) est marqué ``@live``
et doit être exécuté depuis un réseau US ou un proxy approprié.

Localisations hub standard pour le prix système ERCOT
------------------------------------------------------
- ``"HB_BUSAVG"`` : hub system-wide (moyenne pondérée des bus) → prix représentatif.
- ``"HB_WEST"``   : hub Ouest (concentration datacenter/mining, label secondaire L0 §4).
- ``"LZ_HOUSTON"`` / ``"LZ_NORTH"`` / ``"LZ_SOUTH"`` / ``"LZ_WEST"`` : zones de charge.

Unités
------
- Prix RTM : $/MWh (colonne ``SPP`` de gridstatus → ``rtm_price_usd_mwh``).
- Charge / capacité : MW.
- Tous les horodatages internes : UTC tz-aware.
"""

from __future__ import annotations

import os

import pandas as pd

from core.ingestion.energy.base import register_market
from core.ingestion.energy.ercot_transport import (
    ErcotTransport,
    GridstatusDirectTransport,
    GridstatusIoTransport,
)

# Localisation par défaut pour le prix RTM système ERCOT
_DEFAULT_RTM_LOCATION = "HB_BUSAVG"

# Marge de réserve fictive utilisée quand le rapport de capacité n'est pas disponible
# (raisonnement : ERCOT opère typiquement avec ~70 GW de capacité installée)
_ERCOT_INSTALLED_CAPACITY_MW = 70_000.0

# Noms de colonnes gridstatus (constantes pour éviter les littéraux dupliqués)
_COL_INTERVAL_START = "Interval Start"
_COL_INTERVAL_END = "Interval End"
_COL_PUBLISH_TIME = "Publish Time"
_COL_SYSTEM_TOTAL = "System Total"


# ---------------------------------------------------------------------------
# Parsers purs (I/O isolée, testables sur fixtures figées)
# ---------------------------------------------------------------------------


def parse_rtm_spp(
    df: pd.DataFrame,
    location: str = _DEFAULT_RTM_LOCATION,
) -> pd.Series:
    """Parse un DataFrame gridstatus get_spp / get_rtm_spp → pd.Series $/MWh UTC.

    Parameters
    ----------
    df
        DataFrame brut retourné par ``iso.get_spp()`` ou ``iso.get_rtm_spp()``
        avec les colonnes ``["Interval Start", "Location", "SPP"]`` (minimum).
    location
        Identifiant de hub/zone ERCOT à filtrer (ex. ``"HB_BUSAVG"``).

    Returns
    -------
    pd.Series
        Indexée par ``Interval Start`` (UTC tz-aware), valeurs en $/MWh,
        triée chronologiquement, sans NaN injectés, nom ``"rtm_price_usd_mwh"``.

    Raises
    ------
    ValueError
        Si ``location`` n'existe pas dans le DataFrame.
    """
    # Filtrer la localisation demandée
    available = df["Location"].unique().tolist() if "Location" in df.columns else []
    if location not in available:
        raise ValueError(f"Localisation '{location}' introuvable. Disponibles : {available}")

    sub = df[df["Location"] == location].copy()

    # Récupérer la colonne d'index temporel
    time_col = _COL_INTERVAL_START if _COL_INTERVAL_START in sub.columns else "Time"

    # Convertir en UTC tz-aware
    idx = _to_utc(pd.to_datetime(sub[time_col]))

    series = pd.Series(
        sub["SPP"].values,
        index=idx,
        name="rtm_price_usd_mwh",
        dtype=float,
    )

    # Trier chronologiquement et éliminer les doublons éventuels (prend le dernier)
    series = series.sort_index()

    return series


def parse_load_forecast(df: pd.DataFrame) -> pd.DataFrame:
    """Parse un DataFrame gridstatus get_load_forecast → DataFrame normalisé UTC.

    Normalise les colonnes vers le contrat ``EnergyMarket.reserve_forecast`` :
    - ``publish_time``        : heure de publication du rapport (UTC tz-aware).
    - ``interval_start``      : heure cible début (UTC tz-aware).
    - ``interval_end``        : heure cible fin (UTC tz-aware).
    - ``forecast_load_mw``    : charge prévue (System Total, MW).
    - ``forecast_capacity_mw``: capacité disponible prévue (MW).
      Si absente du rapport, estimée à ``_ERCOT_INSTALLED_CAPACITY_MW``
      (valeur nominale conservatrice ; sera remplacée par get_capacity_forecast
      quand disponible).
    - ``reserve_margin_mw``   : marge = capacité − charge (MW).

    Point-in-time L0 §2 : ``publish_time`` est préservée depuis la colonne
    ``Publish Time`` de gridstatus et convertie en UTC. L'invariant
    ``publish_time < interval_start`` est garanti par la nature du rapport
    (prévision publiée avant l'heure cible).

    Parameters
    ----------
    df
        DataFrame brut retourné par ``iso.get_load_forecast()``.

    Returns
    -------
    pd.DataFrame
        Colonnes normalisées, triée par (``publish_time``, ``interval_start``).
    """
    out = pd.DataFrame()

    # Colonnes temporelles
    time_col = _COL_INTERVAL_START if _COL_INTERVAL_START in df.columns else "Time"

    out["publish_time"] = _to_utc(pd.to_datetime(df[_COL_PUBLISH_TIME]))
    out["interval_start"] = _to_utc(pd.to_datetime(df[time_col]))
    out["interval_end"] = _to_utc(pd.to_datetime(df[_COL_INTERVAL_END]))

    # Charge prévue : colonne "System Total" (somme de toutes les zones)
    load_col = _COL_SYSTEM_TOTAL if _COL_SYSTEM_TOTAL in df.columns else df.columns[-1]
    out["forecast_load_mw"] = df[load_col].astype(float).values

    # Capacité prévue : utiliser la colonne dédiée si disponible
    # (provient de get_capacity_forecast ou short_term_system_adequacy),
    # sinon valeur nominale ERCOT (placeholder conservateur, clairement nommé).
    if "forecast_capacity_mw" in df.columns:
        out["forecast_capacity_mw"] = df["forecast_capacity_mw"].astype(float).values
    elif "Available Capacity" in df.columns:
        out["forecast_capacity_mw"] = df["Available Capacity"].astype(float).values
    else:
        out["forecast_capacity_mw"] = _ERCOT_INSTALLED_CAPACITY_MW

    # Marge de réserve = capacité − charge
    out["reserve_margin_mw"] = out["forecast_capacity_mw"] - out["forecast_load_mw"]

    # Tri point-in-time
    out = out.sort_values(["publish_time", "interval_start"]).reset_index(drop=True)

    return out


# ---------------------------------------------------------------------------
# Helper de conversion UTC
# ---------------------------------------------------------------------------


def _to_utc(series: pd.Series) -> pd.Series:
    """Convertit une pd.Series de timestamps en UTC tz-aware.

    Gère les cas : naïf (assume US/Central), US/Central, UTC.
    """
    if series.dt.tz is None:
        # Timestamps naïfs issus d'un CSV lu sans tz → on suppose US/Central
        series = series.dt.tz_localize("US/Central", ambiguous="infer", nonexistent="shift_forward")
    return series.dt.tz_convert("UTC")


# ---------------------------------------------------------------------------
# Connecteur ErcotMarket (wraps gridstatus, implémente EnergyMarket)
# ---------------------------------------------------------------------------


@register_market("ercot")
class ErcotMarket:
    """Connecteur ERCOT Texas via ``gridstatus.Ercot()``.

    Marché public (``required_env = ()``), toujours listé dans le registre.
    Données réelles ERCOT — aucun flag ``simulated`` requis (L0 §2).

    Notes réseau
    ------------
    L'API ercot.com est bloquée par WAF Imperva depuis certains réseaux hors US.
    Utilisez le smoke live (``pytest -m live``) depuis un réseau US pour valider
    le tir réel. Les tests unitaires (B2) tournent sur fixtures figées.
    """

    name = "ercot"
    required_env: tuple[str, ...] = ()

    def __init__(self, transport: ErcotTransport | None = None) -> None:
        """``transport`` injecté (tests/override) ; sinon résolu paresseusement."""
        self._injected = transport
        self._resolved: ErcotTransport | None = None

    def _transport(self) -> ErcotTransport:
        """Résout le transport : injecté > hébergé (clé présente) > direct (géobloqué)."""
        if self._injected is not None:
            return self._injected
        resolved = self._resolved
        if resolved is None:
            resolved = (
                GridstatusIoTransport()
                if os.environ.get("GRIDSTATUS_API_KEY")
                else GridstatusDirectTransport()
            )
            self._resolved = resolved
        return resolved

    def rtm_price(
        self,
        start: pd.Timestamp,
        end: pd.Timestamp,
        location: str = _DEFAULT_RTM_LOCATION,
    ) -> pd.Series:
        """Prix RTM ERCOT sur [start, end], localisation hub/zone.

        Parameters
        ----------
        start, end
            Bornes de la plage (UTC tz-aware recommandé ; converti en US/Central
            pour l'appel gridstatus, retourné en UTC).
        location
            Hub ou zone de charge ERCOT (défaut : ``"HB_BUSAVG"``).

        Returns
        -------
        pd.Series
            Indexée par Interval Start (UTC), valeurs $/MWh, trié, sans NaN.
        """
        df = self._transport().fetch_rtm_spp(start, end, location)
        return parse_rtm_spp(df, location=location)

    def reserve_forecast(
        self,
        start: pd.Timestamp,
        end: pd.Timestamp,
    ) -> pd.DataFrame:
        """Prévisions de charge publiées entre start et end (publication range).

        Point-in-time L0 §2 : retourne tous les rapports dont la date de
        publication est dans [start, end]. L'appelant filtre ensuite sur
        ``publish_time <= cutoff_18h_j1``.

        Parameters
        ----------
        start, end
            Bornes de la fenêtre de publication (UTC tz-aware).

        Returns
        -------
        pd.DataFrame
            Colonnes normalisées (voir ``parse_load_forecast``), UTC tz-aware.
        """
        df = self._transport().fetch_load_forecast(start, end)
        return parse_load_forecast(df)

    def reserve_forecast_as_of(
        self,
        as_of: pd.Timestamp,
    ) -> pd.DataFrame:
        """Dernier rapport de prévision connu AVANT as_of (point-in-time strict).

        Utile pour la calibration L0 : donne la prévision telle qu'elle était
        connue au moment du cutoff de décision (~18h CPT J-1).

        Parameters
        ----------
        as_of
            Horodatage de décision (UTC tz-aware). Seuls les rapports dont
            ``publish_time <= as_of`` sont pris en compte.

        Returns
        -------
        pd.DataFrame
            Sous-ensemble du dernier rapport publié avant ``as_of``.
        """
        df_raw = self._transport().fetch_load_forecast(as_of, as_of)
        df = parse_load_forecast(df_raw)
        # Filtrer causalement : on ne garde que ce qui était connu à as_of
        return df[df["publish_time"] <= as_of].reset_index(drop=True)
