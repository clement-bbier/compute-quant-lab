"""Logique pure du serveur MCP gpu-price (sans dépendance MCP).

Chaque fonction reçoit un :class:`~core.storage.protocols.PriceStore` injecté et renvoie un
dict/list JSON-sérialisable. Le point-in-time passe par ``as_of`` (ISO 8601 UTC, naïf rejeté).
Les prix servis sont **réels** (spot observé) : chaque réponse porte ``provenance="real"``.
"""

from __future__ import annotations

import datetime as dt
from typing import Any


from core.storage.parquet_store import ParquetPriceStore
from core.storage.protocols import PriceStore

#: Étiquette réel/simulé (règle forward-real-simulated.md) — ce serveur ne sert que du réel.
PROVENANCE = "real"


def _parse_instant(value: str | None) -> dt.datetime | None:
    """Parse un instant ISO 8601 en datetime UTC tz-aware ; ``None`` reste ``None``.

    Raises
    ------
    ValueError
        Si ``value`` n'est pas un ISO 8601 valide, ou s'il est naïf (sans fuseau).
    """
    if value is None:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            f"Instant ISO 8601 invalide : {value!r}. Exemple : '2026-06-21T00:00:00+00:00'."
        ) from exc
    if parsed.tzinfo is None:
        raise ValueError(
            f"Instant naïf interdit : {value!r}. Fournir un instant tz-aware UTC "
            "(ex. '2026-06-21T00:00:00+00:00')."
        )
    return parsed.astimezone(dt.timezone.utc)


def list_gpu_models(store: PriceStore, *, as_of: str | None = None) -> list[str]:
    """Liste triée des modèles GPU présents dans le lac (bornée à ``snapshotted_at <= as_of``)."""
    frame = store.read(as_of=_parse_instant(as_of))
    if frame.empty:
        return []
    return sorted(frame["gpu_model"].unique().tolist())


def latest_price(
    store: PriceStore,
    gpu_model: str,
    *,
    lease_type: str = "on_demand",
    as_of: str | None = None,
) -> dict[str, Any]:
    """Dernier prix par source pour ``gpu_model``/``lease_type`` (réel) + résumé min/médian/max."""
    raise NotImplementedError


def price_history(
    store: PriceStore,
    gpu_model: str,
    *,
    start: str | None = None,
    as_of: str | None = None,
    source: str | None = None,
    lease_type: str | None = None,
) -> dict[str, Any]:
    """Série temporelle ordonnée des relevés (réel) de ``gpu_model`` dans ``[start, as_of]``."""
    raise NotImplementedError


def summary_stats(
    store: PriceStore,
    gpu_model: str,
    *,
    lease_type: str | None = None,
    as_of: str | None = None,
) -> dict[str, Any]:
    """Stats descriptives (réel) des prix de ``gpu_model``, bornées au point-in-time ``as_of``."""
    raise NotImplementedError


def run_query(store: ParquetPriceStore, sql: str) -> dict[str, Any]:
    """Exécute ``sql`` (DuckDB **brut**) sur la vue ``prices`` du lac. Aucun garde point-in-time."""
    raise NotImplementedError
