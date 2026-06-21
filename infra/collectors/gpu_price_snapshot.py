"""Collecteur de prix GPU — accumule l'historique compute jour après jour.

L'historique des prix de location GPU n'existe PAS rétroactivement : les marketplaces
n'exposent que le prix courant. On le construit donc en relevant (snapshot) régulièrement
le prix live et en l'horodatant. Planifier ce script via cron (ex. toutes les heures).

**Double écriture (transition Phase 0)** : chaque relevé est persisté dans deux backends.

- **CSV** via :class:`~core.ingestion.snapshot_store.CsvSnapshotStore` — inchangé, lu par
  l'indice P04 tant que la convergence ne l'a pas re-pointé sur le Parquet.
- **Parquet** via :class:`~core.storage.parquet_store.ParquetPriceStore` — le nouveau cold
  store versionné DVC, colonne/typé, qui **conserve la distribution** des offres (là où la
  dédup CSV ``(t, source, modèle, bail)`` l'écrase). Cf. handoff convergence « fix distribution ».

Les deux écritures sont **idempotentes** : relancer le collecteur ne crée pas de doublon.
Le relevé live réel vient de :func:`core.ingestion.gpu_market.fetch_live_gpu_prices`
(Vast.ai / RunPod ; clés via ``.env``).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Sequence

from core.ingestion.gpu_market import fetch_live_gpu_prices
from core.ingestion.protocols import Snapshot
from core.ingestion.snapshot_store import CsvSnapshotStore
from core.storage import ParquetPriceStore, snapshots_to_frame

logger = logging.getLogger(__name__)

SNAPSHOT_DIR = Path(__file__).resolve().parents[2] / "data" / "snapshots"


def snapshot(
    csv_store: CsvSnapshotStore | None = None,
    parquet_store: ParquetPriceStore | None = None,
    *,
    fetch: Callable[[], Sequence[Snapshot]] = fetch_live_gpu_prices,
) -> tuple[Path, int]:
    """Relève le prix live et le persiste en double (CSV P04 + cold store Parquet).

    Parameters
    ----------
    csv_store
        Store CSV (P04). Par défaut : ``data/snapshots/``.
    parquet_store
        Cold store Parquet. Par défaut : ``data/snapshots/`` (coexiste avec les CSV).
    fetch
        Source des relevés (injectable pour les tests). Par défaut : le live marketplace.

    Returns
    -------
    tuple[pathlib.Path, int]
        Le fichier CSV écrit et le nombre de lignes **neuves** ajoutées au lac Parquet.
    """
    csv_store = csv_store or CsvSnapshotStore(SNAPSHOT_DIR)
    parquet_store = parquet_store or ParquetPriceStore(SNAPSHOT_DIR)

    rows = list(fetch())
    csv_path = csv_store.append(rows)
    written = parquet_store.write(snapshots_to_frame(rows))

    logger.info(
        "Snapshot collecté : %d relevés -> CSV %s ; %d ligne(s) neuve(s) -> Parquet %s",
        len(rows),
        csv_path,
        written,
        parquet_store.root,
    )
    return csv_path, written


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    snapshot()
