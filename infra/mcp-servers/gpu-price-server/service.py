"""Logique pure du serveur MCP gpu-price (sans dépendance MCP).

Chaque fonction reçoit un :class:`~core.storage.protocols.PriceStore` injecté et renvoie un
dict/list JSON-sérialisable. Le point-in-time passe par ``as_of`` (ISO 8601 UTC, naïf rejeté).
Les prix servis sont **réels** (spot observé) : chaque réponse porte ``provenance="real"``.
"""

from __future__ import annotations

import datetime as dt
import statistics
from typing import Any

import pandas as pd

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


def _latest_row_per_source(subset: pd.DataFrame) -> pd.DataFrame:
    """Par source : l'instant le plus récent, puis l'offre la moins chère à cet instant."""
    freshest_per_source = subset.groupby("source")["snapshotted_at"].transform("max")
    freshest = subset[subset["snapshotted_at"] == freshest_per_source]
    cheapest_idx = freshest.groupby("source")["price_usd_per_hour"].idxmin()
    return freshest.loc[cheapest_idx].sort_values("source")


def latest_price(
    store: PriceStore,
    gpu_model: str,
    *,
    lease_type: str = "on_demand",
    as_of: str | None = None,
) -> dict[str, Any]:
    """Dernier prix par source pour ``gpu_model``/``lease_type`` (réel) + résumé min/médian/max."""
    frame = store.read(as_of=_parse_instant(as_of))
    subset = frame[(frame["gpu_model"] == gpu_model) & (frame["lease_type"] == lease_type)]
    if subset.empty:
        available = sorted(frame["gpu_model"].unique().tolist()) if not frame.empty else []
        return {
            "gpu_model": gpu_model,
            "lease_type": lease_type,
            "found": False,
            "provenance": PROVENANCE,
            "message": f"Aucun relevé pour gpu_model={gpu_model!r}, lease_type={lease_type!r}.",
            "available_models": available,
        }
    latest = _latest_row_per_source(subset)
    by_source = [
        {
            "source": row.source,
            "price_usd_per_hour": float(row.price_usd_per_hour),
            "availability": int(row.availability),
            "snapshotted_at": row.snapshotted_at.isoformat(),
        }
        for row in latest.itertuples(index=False)
    ]
    prices = [item["price_usd_per_hour"] for item in by_source]
    return {
        "gpu_model": gpu_model,
        "lease_type": lease_type,
        "found": True,
        "provenance": PROVENANCE,
        "as_of": subset["snapshotted_at"].max().isoformat(),
        "by_source": by_source,
        "summary": {
            "min": min(prices),
            "median": round(statistics.median(prices), 10),
            "max": max(prices),
            "n_sources": len(prices),
        },
    }


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
    cutoff = _parse_instant(as_of)
    start_dt = _parse_instant(start)
    frame = store.read(as_of=cutoff, source=source)
    subset = frame[frame["gpu_model"] == gpu_model]
    if lease_type is not None:
        subset = subset[subset["lease_type"] == lease_type]
    if start_dt is not None:
        subset = subset[subset["snapshotted_at"] >= pd.Timestamp(start_dt)]
    subset = subset.sort_values("snapshotted_at")
    observations = [
        {
            "snapshotted_at": row.snapshotted_at.isoformat(),
            "source": row.source,
            "lease_type": row.lease_type,
            "price_usd_per_hour": float(row.price_usd_per_hour),
            "availability": int(row.availability),
        }
        for row in subset.itertuples(index=False)
    ]
    return {
        "gpu_model": gpu_model,
        "start": start_dt.isoformat() if start_dt is not None else None,
        "as_of": cutoff.isoformat() if cutoff is not None else None,
        "provenance": PROVENANCE,
        "n": len(observations),
        "observations": observations,
    }


def summary_stats(
    store: PriceStore,
    gpu_model: str,
    *,
    lease_type: str | None = None,
    as_of: str | None = None,
) -> dict[str, Any]:
    """Stats descriptives (réel) des prix de ``gpu_model``, bornées au point-in-time ``as_of``."""
    cutoff = _parse_instant(as_of)
    frame = store.read(as_of=cutoff)
    subset = frame[frame["gpu_model"] == gpu_model]
    if lease_type is not None:
        subset = subset[subset["lease_type"] == lease_type]
    if subset.empty:
        return {
            "gpu_model": gpu_model,
            "found": False,
            "provenance": PROVENANCE,
            "n": 0,
            "message": f"Aucun relevé pour gpu_model={gpu_model!r}.",
        }
    prices = subset["price_usd_per_hour"]
    overall = {
        "count": int(prices.count()),
        "min": float(prices.min()),
        "max": float(prices.max()),
        "mean": float(prices.mean()),
        "median": float(prices.median()),
        "std": float(prices.std(ddof=0)),  # population : défini même pour n=1
    }
    by_source = [
        {
            "source": str(src),
            "count": int(grp["price_usd_per_hour"].count()),
            "min": float(grp["price_usd_per_hour"].min()),
            "max": float(grp["price_usd_per_hour"].max()),
            "mean": float(grp["price_usd_per_hour"].mean()),
            "median": float(grp["price_usd_per_hour"].median()),
        }
        for src, grp in subset.groupby("source")
    ]
    return {
        "gpu_model": gpu_model,
        "found": True,
        "provenance": PROVENANCE,
        "as_of": cutoff.isoformat()
        if cutoff is not None
        else subset["snapshotted_at"].max().isoformat(),
        "n": int(prices.count()),
        "overall": overall,
        "by_source": sorted(by_source, key=lambda d: d["source"]),
        "first_obs_at": subset["snapshotted_at"].min().isoformat(),
        "last_obs_at": subset["snapshotted_at"].max().isoformat(),
    }


def run_query(store: ParquetPriceStore, sql: str) -> dict[str, Any]:
    """Exécute ``sql`` (DuckDB **brut**) sur la vue ``prices`` du lac. Aucun garde point-in-time."""
    raise NotImplementedError
