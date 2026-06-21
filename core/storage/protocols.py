"""Abstractions de stockage du labo (DI / SOLID).

Les projets dépendent de ces **Protocols**, jamais d'un backend concret : changer de
backend = nouvelle implémentation, zéro modif des consommateurs (OCP). Même patron que
les sources d'ingestion P04. Cette couche est posée *avant* tout backend précis pour
rendre indolore la migration entre phases (cf. ``docs/storage-roadmap.md`` §2).

Trois rôles, un par phase de la roadmap :

- :class:`PriceStore` — **cold store** historique, immuable, point-in-time (Phase 0–1).
  Implémenté ici par :class:`~core.storage.parquet_store.ParquetPriceStore`.
- :class:`TickStream` — flux de ticks temps réel (Phase 2, Redpanda). **Stub documenté.**
- :class:`HotCache` — dernier prix/feature en faible latence (Phase 4, Redis). **Stub.**

Seul ``PriceStore`` est implémenté dans ce lot : ``TickStream`` et ``HotCache`` fixent
le contrat des phases institutionnelles sans préjuger du backend (anti-sur-ingénierie).
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Iterator, Mapping, Protocol, runtime_checkable

import pandas as pd


@runtime_checkable
class PriceStore(Protocol):
    """Cold store append-only et point-in-time de relevés de prix compute/énergie.

    Contrat minimal commun à Parquet (Phase 0) puis Timescale (Phase 3) : un writer
    idempotent et un reader point-in-time. Les consommateurs (features, backtests,
    modèles) ne voient que ce protocole.
    """

    def write(self, frame: pd.DataFrame) -> int:
        """Persiste ``frame`` (append-only, idempotent) ; renvoie le nb de lignes neuves."""
        ...

    def read(self, *, as_of: dt.datetime | None = None, source: str | None = None) -> pd.DataFrame:
        """Relit le store ; ``as_of`` borne au point-in-time (``snapshotted_at <= as_of``)."""
        ...


@runtime_checkable
class TickStream(Protocol):
    """Flux de ticks temps réel — **stub Phase 2** (Redpanda / Kafka-compatible).

    Non implémenté dans ce lot : le streaming n'a de sens qu'après avoir décidé de
    ticker en intraday (cf. roadmap §3 Phase 2, §4 anti-sur-ingénierie). Présent pour
    fixer le contrat afin que les sinks cold/hot s'y branchent sans refonte.
    """

    def produce(self, tick: Mapping[str, Any]) -> None:
        """Publie un tick sur le topic (ex. ``compute.prices``)."""
        ...

    def consume(self) -> Iterator[Mapping[str, Any]]:
        """Itère les ticks pour alimenter un sink (cold Parquet, hot Timescale, Redis)."""
        ...


@runtime_checkable
class HotCache(Protocol):
    """Cache de serving faible latence — **stub Phase 4** (Redis).

    Non implémenté : à activer quand un consommateur live existe (pricer spark spread
    live, inférence P09, desk P10, dashboard). Sert le serving/monitoring, **jamais**
    la reproductibilité (qui lit toujours le cold store versionné).
    """

    def set_latest(self, key: str, value: Mapping[str, Any]) -> None:
        """Mémorise le dernier prix/feature pour ``key``."""
        ...

    def get_latest(self, key: str) -> Mapping[str, Any] | None:
        """Renvoie le dernier prix/feature pour ``key`` (ou ``None`` si absent)."""
        ...
