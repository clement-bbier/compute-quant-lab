"""Protocoles et types de la jambe compute (ingestion).

Définit les abstractions injectables (DI / SOLID) du sous-système d'ingestion
compute et les types de données immuables qui circulent entre les couches :
source d'indice → store de snapshots → agrégation → indice spot propre.

Deux familles d'abstractions, toutes interchangeables par injection (OCP) :

- **sources** (:class:`ComputeIndexSource`) : d'où viennent les prix (Silicon Data,
  proxy marketplace, …) ;
- **agrégation** (:class:`OutlierFilter`, :class:`IndexEstimator`) : comment des prix
  par-venue hétérogènes deviennent un prix canonique. Ajouter une méthode = nouvelle
  implémentation, sans toucher au cœur ``build_spot_index``.

Tous les horodatages sont UTC timezone-aware (règle d'intégrité des données) : les
dataclasses normalisent à la construction et refusent un datetime naïf, si bien qu'un
état illégal (instant ambigu) ne peut pas être représenté.

Unité de prix : USD par GPU·heure ($/GPU·h), conformément au cadrage P04.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Protocol, Sequence, runtime_checkable


def ensure_utc(ts: dt.datetime) -> dt.datetime:
    """Convertit ``ts`` en UTC ; lève si ``ts`` est naïf.

    Parameters
    ----------
    ts
        Horodatage timezone-aware. Un datetime naïf est rejeté pour éviter toute
        ambiguïté point-in-time.

    Returns
    -------
    datetime.datetime
        Le même instant, exprimé en UTC.

    Raises
    ------
    ValueError
        Si ``ts`` n'a pas de fuseau (datetime naïf).
    """
    if ts.tzinfo is None:
        raise ValueError("Horodatage naïf interdit : fournir un datetime tz-aware (UTC).")
    return ts.astimezone(dt.timezone.utc)


@dataclass(frozen=True)
class Snapshot:
    """Relevé de prix d'une source compute à un instant donné (unité brute).

    Unité append-only stockée et dédupliquée par le :class:`SnapshotStore`. Le prix
    est en USD par GPU·heure. ``lease_type`` distingue on-demand / spot / reserved :
    on n'agrège jamais des types de bail différents (standard Silicon Data).

    Les champs descriptifs optionnels (``region``, ``gpu_memory_gb``, ``vcpu``,
    ``ram_gb``, ``disk_gb``, ``provider_detail``) enrichissent le relevé quand l'API
    de la venue les expose. Ils N'entrent PAS dans ``dedup_key`` : l'idempotence
    reste (instant, source, modèle, bail) — les métadonnées hardware ne brisent pas
    la dédup point-in-time.
    """

    snapshotted_at: dt.datetime
    source: str
    gpu_model: str
    price_usd_per_hour: float
    lease_type: str = "on_demand"
    availability: int = 0
    # ── champs descriptifs optionnels (compat ascendante : tout existant compile) ──
    region: str | None = None
    gpu_memory_gb: float | None = None
    vcpu: int | None = None
    ram_gb: float | None = None
    disk_gb: float | None = None
    provider_detail: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshotted_at", ensure_utc(self.snapshotted_at))

    @property
    def dedup_key(self) -> tuple[str, str, str, str]:
        """Clé naturelle d'idempotence : (instant ISO, source, modèle GPU, type de bail)."""
        return (self.snapshotted_at.isoformat(), self.source, self.gpu_model, self.lease_type)


@dataclass(frozen=True)
class VenueRate:
    """Taux représentatif d'une venue (marketplace) entrant dans l'agrégation.

    Produit en réduisant, par source, les snapshots frais au plus récent. C'est l'unité
    que voient les stratégies d'agrégation (:class:`OutlierFilter`, :class:`IndexEstimator`).
    """

    source: str
    rate: float
    availability: int
    snapshotted_at: dt.datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshotted_at", ensure_utc(self.snapshotted_at))


@dataclass(frozen=True)
class SpotIndexPoint:
    """Valeur canonique de l'indice spot compute pour un modèle à un instant.

    Produit par ``build_spot_index`` en agrégeant plusieurs venues. ``method`` trace la
    config d'agrégation (estimateur + filtre) et ``oldest_obs_at`` l'âge du plus vieux
    relevé retenu : ensemble ils rendent chaque point **auditable et rejouable**.
    """

    as_of: dt.datetime
    gpu_model: str
    lease_type: str
    price_usd_per_hour: float
    n_sources: int
    method: str
    oldest_obs_at: dt.datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "as_of", ensure_utc(self.as_of))
        object.__setattr__(self, "oldest_obs_at", ensure_utc(self.oldest_obs_at))


@runtime_checkable
class ComputeIndexSource(Protocol):
    """Source de prix compute (Silicon Data, proxy marketplace, …).

    Abstraction d'injection : l'indice agrège des sources via ce protocole, donc
    ajouter une marketplace = nouvelle implémentation sans toucher au cœur (OCP).
    """

    def fetch(self, start: dt.datetime, end: dt.datetime) -> Sequence[Snapshot]:
        """Renvoie les relevés disponibles dans la fenêtre ``[start, end]`` (UTC)."""
        ...


@runtime_checkable
class SnapshotStore(Protocol):
    """Stockage append-only et idempotent des snapshots de prix compute."""

    def append(self, rows: Iterable[Snapshot]) -> Path:
        """Append ``rows`` en dédupliquant par clé naturelle ; renvoie le fichier écrit."""
        ...

    def load(self) -> list[Snapshot]:
        """Recharge tous les snapshots stockés (ordre non garanti)."""
        ...


@runtime_checkable
class OutlierFilter(Protocol):
    """Stratégie de rejet des taux aberrants avant agrégation (interchangeable)."""

    @property
    def name(self) -> str:
        """Identifiant court tracé dans ``SpotIndexPoint.method`` (ex. ``mad2.5``)."""
        ...

    def filter(self, rates: Sequence[VenueRate]) -> list[VenueRate]:
        """Renvoie le sous-ensemble des taux conservés (outliers retirés)."""
        ...


@runtime_checkable
class IndexEstimator(Protocol):
    """Stratégie d'agrégation de taux par-venue en un prix canonique (interchangeable)."""

    @property
    def name(self) -> str:
        """Identifiant court tracé dans ``SpotIndexPoint.method`` (ex. ``trimmed_mean20``)."""
        ...

    def estimate(self, rates: Sequence[VenueRate]) -> float:
        """Agrège les ``rates`` (non vides) en un unique prix $/GPU·h."""
        ...
