"""Stockage append-only idempotent des snapshots de prix compute (CSV mensuels).

L'historique des prix de location GPU n'existe pas rétroactivement : on l'accumule en
relevant le prix live et en l'horodatant. ``CsvSnapshotStore`` matérialise cette série
propriétaire dans ``data/snapshots/`` (versionnée DVC), en garantissant l'**idempotence** :
ré-appender un relevé déjà présent (même clé naturelle) est un no-op. Indispensable pour
un collecteur planifié rejouable sans créer de doublons.
"""

from __future__ import annotations

import csv
import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Iterable

from core.ingestion.protocols import Snapshot

_FIELDS: list[str] = [
    "snapshotted_at",
    "source",
    "gpu_model",
    "lease_type",
    "price_usd_per_hour",
    "availability",
]


@dataclass
class CsvSnapshotStore:
    """Implémentation :class:`~core.ingestion.protocols.SnapshotStore` en CSV mensuels.

    Parameters
    ----------
    directory
        Répertoire des fichiers ``gpu_prices_YYYYMM.csv`` (créé si absent).
    """

    directory: Path
    FIELDS: ClassVar[list[str]] = _FIELDS

    def __post_init__(self) -> None:
        self.directory = Path(self.directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def _file_for(self, ts: dt.datetime) -> Path:
        return self.directory / f"gpu_prices_{ts:%Y%m}.csv"

    def load(self) -> list[Snapshot]:
        """Recharge tous les snapshots stockés (tous fichiers mensuels confondus)."""
        out: list[Snapshot] = []
        for path in sorted(self.directory.glob("gpu_prices_*.csv")):
            with path.open(newline="") as f:
                for row in csv.DictReader(f):
                    out.append(
                        Snapshot(
                            snapshotted_at=dt.datetime.fromisoformat(row["snapshotted_at"]),
                            source=row["source"],
                            gpu_model=row["gpu_model"],
                            price_usd_per_hour=float(row["price_usd_per_hour"]),
                            lease_type=row["lease_type"],
                            availability=int(row["availability"]),
                        )
                    )
        return out

    def append(self, rows: Iterable[Snapshot]) -> Path:
        """Append ``rows`` en dédupliquant par clé naturelle ; renvoie le dernier fichier écrit."""
        seen: set[tuple[str, str, str, str]] = {s.dedup_key for s in self.load()}
        written: Path | None = None
        for snap in rows:
            if snap.dedup_key in seen:
                continue
            seen.add(snap.dedup_key)
            path = self._file_for(snap.snapshotted_at)
            new_file = not path.exists()
            with path.open("a", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=_FIELDS)
                if new_file:
                    writer.writeheader()
                writer.writerow(
                    {
                        "snapshotted_at": snap.snapshotted_at.isoformat(),
                        "source": snap.source,
                        "gpu_model": snap.gpu_model,
                        "lease_type": snap.lease_type,
                        "price_usd_per_hour": snap.price_usd_per_hour,
                        "availability": snap.availability,
                    }
                )
            written = path
        return written if written is not None else self.directory
