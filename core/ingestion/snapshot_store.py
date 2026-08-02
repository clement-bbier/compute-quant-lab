"""Idempotent append-only store for compute price snapshots (monthly CSV files).

GPU rental price history does not exist retroactively: it has to be accumulated by
reading the live price and stamping it. ``CsvSnapshotStore`` materialises that
proprietary series under ``data/snapshots/`` (tracked as plain git files) and
guarantees **idempotence**: re-appending a reading that is already stored (same
natural key) is a no-op. That is what makes a scheduled collector safe to replay
without creating duplicates.

Provenance column (``simulated``, V7.3): mandatory on :class:`Snapshot`, but a
*monthly* CSV file is append-only and the live hourly collector will hit an existing
file whose header predates the column within the hour this ships. Unlike the purely
optional descriptive fields (which a legacy header may simply never gain), ``simulated``
must never be silently dropped by ``extrasaction="ignore"`` -- so ``append`` rewrites an
out-of-date header **once**, in place, the first time it needs to write a column the
on-disk header lacks (see :meth:`CsvSnapshotStore._ensure_header_has`). Existing data
rows are untouched (short rows, not corrupted ones); ``load`` backfills their missing
``simulated`` cell to ``False`` -- documented provenance (every row ever written by this
store came from a real collector run; there is no synthetic compute-price fallback),
not a guessed default.
"""

from __future__ import annotations

import csv
import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Iterable

from core.ingestion.protocols import Snapshot
from core.utils.coerce import lenient_float, lenient_int, lenient_str
from core.utils.logging import get_logger

logger = get_logger(__name__)

_CORE_FIELDS: list[str] = [
    "snapshotted_at",
    "source",
    "gpu_model",
    "lease_type",
    "price_usd_per_hour",
    "availability",
]

#: Optional descriptive columns exposed by richer venue APIs (wave W2). Absent from
#: legacy 6-column CSV files, which stay readable: missing values decode to ``None``.
_OPTIONAL_FIELDS: list[str] = [
    "region",
    "gpu_memory_gb",
    "vcpu",
    "ram_gb",
    "disk_gb",
    "provider_detail",
]

#: Mandatory provenance column (V7.3): unlike ``_OPTIONAL_FIELDS``, a legacy file missing
#: it is upgraded in place on next append (see module docstring) rather than silently
#: dropping the value forever.
_PROVENANCE_FIELDS: list[str] = ["simulated"]

_FIELDS: list[str] = [*_CORE_FIELDS, *_OPTIONAL_FIELDS, *_PROVENANCE_FIELDS]


@dataclass
class CsvSnapshotStore:
    """Monthly-CSV implementation of :class:`~core.ingestion.protocols.SnapshotStore`.

    Parameters
    ----------
    directory
        Directory holding the ``gpu_prices_YYYYMM.csv`` files (created if absent).
    """

    directory: Path
    FIELDS: ClassVar[list[str]] = _FIELDS

    def __post_init__(self) -> None:
        self.directory = Path(self.directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def _file_for(self, ts: dt.datetime) -> Path:
        return self.directory / f"gpu_prices_{ts:%Y%m}.csv"

    def load(self) -> list[Snapshot]:
        """Reload every stored snapshot, across all monthly files.

        Legacy 6-column files stay readable: the optional descriptive columns are
        simply absent, and decode to ``None``. Empty strings decode to ``None`` too,
        so a row written with an unset optional field round-trips faithfully.

        A row predating the ``simulated`` column (empty or absent cell) backfills to
        ``False`` -- documented provenance, not a guessed default (see module docstring).
        """
        out: list[Snapshot] = []
        for path in sorted(self.directory.glob("gpu_prices_*.csv")):
            with path.open(newline="") as f:
                for row in csv.DictReader(f):
                    simulated_raw = row.get("simulated")
                    out.append(
                        Snapshot(
                            snapshotted_at=dt.datetime.fromisoformat(row["snapshotted_at"]),
                            source=row["source"],
                            gpu_model=row["gpu_model"],
                            price_usd_per_hour=float(row["price_usd_per_hour"]),
                            lease_type=row["lease_type"],
                            availability=int(row["availability"]),
                            region=lenient_str(row.get("region") or None),
                            gpu_memory_gb=lenient_float(row.get("gpu_memory_gb") or None),
                            vcpu=lenient_int(row.get("vcpu") or None),
                            ram_gb=lenient_float(row.get("ram_gb") or None),
                            disk_gb=lenient_float(row.get("disk_gb") or None),
                            provider_detail=lenient_str(row.get("provider_detail") or None),
                            simulated=simulated_raw == "True" if simulated_raw else False,
                        )
                    )
        return out

    def _header_of(self, path: Path) -> list[str]:
        """Column names of an existing file, so appends match its actual layout."""
        with path.open(newline="") as f:
            header = next(csv.reader(f), [])
        return header or list(_FIELDS)

    def _ensure_header_has(self, path: Path, header: list[str], required: str) -> list[str]:
        """Rewrite ``path``'s header line in place if it lacks ``required``; return the new header.

        Used only for :data:`_PROVENANCE_FIELDS` (``simulated``), never for the purely
        optional descriptive columns: those may stay legitimately absent from an old
        header forever, but provenance must never be silently dropped by
        ``extrasaction="ignore"`` once it exists on every ``Snapshot``. Only the single
        header line is touched -- O(1), independent of the file's row count -- existing
        data rows keep their original (shorter) column count and are backfilled on
        :meth:`load` instead of being rewritten.
        """
        if required in header:
            return header
        upgraded = [*header, required]
        with path.open() as f:
            body = f.read().split("\n", 1)
        rest = body[1] if len(body) > 1 else ""
        with path.open("w", newline="") as f:
            csv.writer(f).writerow(upgraded)
            f.write(rest)
        logger.info(
            "CsvSnapshotStore %s: upgraded header to add '%s' (existing rows unaffected)",
            path,
            required,
        )
        return upgraded

    def append(self, rows: Iterable[Snapshot]) -> Path:
        """Append ``rows``, deduplicating on the natural key; return the last file written.

        A file created by this version carries every column in :data:`_FIELDS`. A
        pre-existing file whose header lacks a purely optional descriptive column (e.g.
        the legacy 6-column layout) keeps that gap: rows appended to it are projected
        onto its own header via ``extrasaction="ignore"``, since retroactively enriching
        hardware metadata is not this store's job. The mandatory provenance column
        (``simulated``) is different: a header missing it is upgraded in place first (see
        :meth:`_ensure_header_has`), so it is never silently dropped. Use
        :mod:`core.storage.migrate` to lift legacy CSV files into the Parquet lake.
        """
        seen: set[tuple[str, str, str, str]] = {s.dedup_key for s in self.load()}
        written: Path | None = None
        n_written = 0
        n_deduped = 0
        for snap in rows:
            if snap.dedup_key in seen:
                n_deduped += 1
                continue
            seen.add(snap.dedup_key)
            path = self._file_for(snap.snapshotted_at)
            new_file = not path.exists()
            fieldnames = list(_FIELDS) if new_file else self._header_of(path)
            if not new_file:
                for provenance_field in _PROVENANCE_FIELDS:
                    fieldnames = self._ensure_header_has(path, fieldnames, provenance_field)
            record = {
                "snapshotted_at": snap.snapshotted_at.isoformat(),
                "source": snap.source,
                "gpu_model": snap.gpu_model,
                "lease_type": snap.lease_type,
                "price_usd_per_hour": snap.price_usd_per_hour,
                "availability": snap.availability,
                "region": snap.region,
                "gpu_memory_gb": snap.gpu_memory_gb,
                "vcpu": snap.vcpu,
                "ram_gb": snap.ram_gb,
                "disk_gb": snap.disk_gb,
                "provider_detail": snap.provider_detail,
                "simulated": snap.simulated,
            }
            with path.open("a", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore", restval="")
                if new_file:
                    writer.writeheader()
                writer.writerow({k: "" if v is None else v for k, v in record.items()})
            written = path
            n_written += 1
        logger.info(
            "CsvSnapshotStore %s: %d new row(s) written, %d deduplicated",
            self.directory,
            n_written,
            n_deduped,
        )
        return written if written is not None else self.directory
