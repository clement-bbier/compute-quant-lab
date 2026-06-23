"""Transports ERCOT injectables — egress direct (géobloqué) vs hébergé (US).

Sépare le *fetch* (où l'on prend la donnée) de la *normalisation* (parsers purs de
``ercot.py``). Deux transports interchangeables derrière un même protocole :

- :class:`GridstatusDirectTransport` — ``gridstatus.Ercot()`` qui tape ercot.com en
  direct. **Géobloqué** (WAF Imperva) depuis les IP non-US.
- :class:`GridstatusIoTransport` — API hébergée **GridStatus.io** (serveurs US) via
  ``gridstatusio.GridStatusClient``. Contourne le géoblocage légitimement. Clé via
  ``GRIDSTATUS_API_KEY``.

Chaque transport ramène ses frames au **schéma canonique gridstatus** (colonnes
``"Interval Start"`` / ``"Location"`` / ``"SPP"`` / ``"Publish Time"`` / ``"System
Total"``) que les parsers de ``ercot.py`` consomment déjà — zéro duplication de parsing.

⚠️ Schéma hébergé *présumé* (snake_case + suffixes ``_utc``), construit depuis la doc
publique GridStatus.io. **À confirmer par le test live** (``-m live`` avec une vraie
clé) : si une colonne diffère, l'ajustement est localisé dans les mappers ci-dessous.
Quota free plan : 500k lignes/mois → toujours passer ``limit`` sur les gros tirages.
"""

from __future__ import annotations

import os
from typing import Protocol

import pandas as pd

#: Dataset IDs de l'API hébergée GridStatus.io (à confirmer via ``list_datasets()``).
RTM_DATASET = "ercot_spp_real_time_15_min"
FORECAST_DATASET = "ercot_load_forecast"
ADEQUACY_DATASET = "ercot_short_term_system_adequacy"

#: Colonne de capacité hébergée retenue pour la marge de réserve L0 (à confirmer live).
_HOSTED_CAPACITY_COL = "available_capacity_generation"


class ErcotTransport(Protocol):
    """Abstraction de fetch ERCOT → frames au schéma canonique gridstatus."""

    def fetch_rtm_spp(self, start: pd.Timestamp, end: pd.Timestamp, location: str) -> pd.DataFrame:
        """Frame RTM SPP brut (colonnes canoniques ``Interval Start``/``Location``/``SPP``)."""
        ...

    def fetch_load_forecast(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        """Frame prévision de charge brut (colonnes canoniques ``Publish Time``/…)."""
        ...

    def fetch_system_adequacy(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        """Frame STSA brut (capacité prévue, colonne ``Available Capacity Generation``)."""
        ...


# ---------------------------------------------------------------------------
# Transport direct (gridstatus.Ercot — géobloqué hors US)
# ---------------------------------------------------------------------------


class GridstatusDirectTransport:
    """Tape ercot.com en direct via ``gridstatus``. Géobloqué (WAF) hors US."""

    def __init__(self) -> None:
        self._iso: object | None = None  # lazy import/init

    def _get_iso(self) -> object:
        if self._iso is None:
            import gridstatus  # noqa: PLC0415

            self._iso = gridstatus.Ercot()
        return self._iso

    def fetch_rtm_spp(self, start: pd.Timestamp, end: pd.Timestamp, location: str) -> pd.DataFrame:
        import gridstatus  # noqa: PLC0415

        return self._get_iso().get_spp(  # type: ignore[attr-defined,no-any-return]
            date=start,
            end=end,
            market=gridstatus.Markets.REAL_TIME_15_MIN,
            locations=[location],
        )

    def fetch_load_forecast(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        return self._get_iso().get_load_forecast(  # type: ignore[attr-defined,no-any-return]
            date=start, end=end
        )

    def fetch_system_adequacy(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        return self._get_iso().get_short_term_system_adequacy(  # type: ignore[attr-defined,no-any-return]
            date=start, end=end
        )


# ---------------------------------------------------------------------------
# Transport hébergé (GridStatus.io — contourne le géoblocage)
# ---------------------------------------------------------------------------


class GridstatusIoTransport:
    """API hébergée GridStatus.io (US). Clé via ``GRIDSTATUS_API_KEY`` ou injectée.

    Parameters
    ----------
    api_key
        Clé API ; à défaut, lue dans ``GRIDSTATUS_API_KEY`` au premier appel.
    client
        Client déjà construit (injection de test). Si fourni, ``api_key`` est ignorée.
    limit
        Plafond de lignes par requête (quota free = 500k/mois). ``None`` = pas de plafond.
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        client: object | None = None,
        limit: int | None = None,
    ) -> None:
        self._api_key = api_key
        self._client = client
        self._limit = limit

    def _get_client(self) -> object:
        if self._client is None:
            from gridstatusio import GridStatusClient  # noqa: PLC0415

            key = self._api_key or os.environ.get("GRIDSTATUS_API_KEY")
            if not key:
                raise RuntimeError("GRIDSTATUS_API_KEY absente : transport hébergé indisponible")
            self._client = GridStatusClient(api_key=key)
        return self._client

    def fetch_rtm_spp(self, start: pd.Timestamp, end: pd.Timestamp, location: str) -> pd.DataFrame:
        raw = self._get_client().get_dataset(  # type: ignore[attr-defined]
            RTM_DATASET,
            start=_date_str(start),
            end=_date_str(end),
            filter_column="location",
            filter_value=location,
            limit=self._limit,
        )
        return _hosted_rtm_to_canonical(raw)

    def fetch_load_forecast(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        raw = self._get_client().get_dataset(  # type: ignore[attr-defined]
            FORECAST_DATASET,
            start=_date_str(start),
            end=_date_str(end),
            limit=self._limit,
        )
        return _hosted_forecast_to_canonical(raw)

    def fetch_system_adequacy(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        raw = self._get_client().get_dataset(  # type: ignore[attr-defined]
            ADEQUACY_DATASET,
            start=_date_str(start),
            end=_date_str(end),
            limit=self._limit,
        )
        return _hosted_adequacy_to_canonical(raw)


# ---------------------------------------------------------------------------
# Mappers schéma hébergé → schéma canonique gridstatus (point de confirmation live)
# ---------------------------------------------------------------------------


def _date_str(ts: pd.Timestamp) -> str:
    """Borne de requête au format ISO date (l'API hébergée accepte 'YYYY-MM-DD')."""
    return pd.Timestamp(ts).strftime("%Y-%m-%d")


def _hosted_rtm_to_canonical(df: pd.DataFrame) -> pd.DataFrame:
    """Renomme le schéma hébergé SPP vers le canonique gridstatus (temps UTC tz-aware)."""
    return pd.DataFrame(
        {
            "Interval Start": pd.to_datetime(df["interval_start_utc"], utc=True),
            "Interval End": pd.to_datetime(df["interval_end_utc"], utc=True),
            "Location": df["location"].to_numpy(),
            "SPP": df["spp"].astype(float).to_numpy(),
        }
    )


def _hosted_forecast_to_canonical(df: pd.DataFrame) -> pd.DataFrame:
    """Renomme le schéma hébergé ``ercot_load_forecast`` vers le canonique gridstatus.

    Schéma RÉEL confirmé en live (2026-06) : colonnes ``interval_start_utc`` /
    ``interval_end_utc`` / ``publish_time_utc`` / ``load_forecast`` — prévision de
    charge **system-wide**, un seul jeu par intervalle (pas de dimension modèle).
    """
    return pd.DataFrame(
        {
            "Publish Time": pd.to_datetime(df["publish_time_utc"], utc=True),
            "Interval Start": pd.to_datetime(df["interval_start_utc"], utc=True),
            "Interval End": pd.to_datetime(df["interval_end_utc"], utc=True),
            "System Total": df["load_forecast"].astype(float).to_numpy(),
        }
    )


def _hosted_adequacy_to_canonical(df: pd.DataFrame) -> pd.DataFrame:
    """Renomme le schéma hébergé ``ercot_short_term_system_adequacy`` vers le canonique.

    STSA est un rapport de **capacité** (PAS de demande). On retient
    ``available_capacity_generation`` (capacité de génération disponible prévue)
    comme capacité de la marge de réserve L0. Nom hébergé à confirmer par le test live.
    """
    return pd.DataFrame(
        {
            "Publish Time": pd.to_datetime(df["publish_time_utc"], utc=True),
            "Interval Start": pd.to_datetime(df["interval_start_utc"], utc=True),
            "Interval End": pd.to_datetime(df["interval_end_utc"], utc=True),
            "Available Capacity Generation": df[_HOSTED_CAPACITY_COL].astype(float).to_numpy(),
        }
    )
